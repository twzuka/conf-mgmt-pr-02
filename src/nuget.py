"""Получение прямых зависимостей конкретной версии пакета NuGet V3."""

import json
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import urlopen
from xml.etree import ElementTree

from .config import check_package, check_url

HTTP_TIMEOUT = 20
HTTP_NOT_FOUND = 404
PACKAGE_BASE_TYPE = "PackageBaseAddress/3.0.0"
MIN_VERSION_PARTS = 3
MAX_VERSION_PARTS = 4


class NuGetError(Exception):
    """Ошибка загрузки или разбора данных NuGet."""


@dataclass(frozen=True)
class Dependency:
    """Прямая зависимость: имя, диапазон версий и целевая платформа."""

    package: str
    version: str
    framework: str


def fetch_bytes(url):
    """Загружает байты по HTTP(S) с ограничением времени ожидания."""
    try:
        with urlopen(url, timeout=HTTP_TIMEOUT) as response:
            return response.read()
    except HTTPError as error:
        if error.code == HTTP_NOT_FOUND:
            message = "ресурс не найден (HTTP 404)"
        else:
            message = f"ошибка HTTP {error.code}"
        raise NuGetError(f"{message}: {url}") from error
    except (URLError, OSError, ValueError) as error:
        raise NuGetError(f"не удалось загрузить {url}: {error}") from error


def get_package_base(repository):
    """Находит адрес PackageBaseAddress в индексе NuGet V3."""
    try:
        index = json.loads(fetch_bytes(repository))
    except (ValueError, UnicodeDecodeError) as error:
        raise NuGetError("индекс репозитория содержит неверный JSON") from error
    if not isinstance(index, dict):
        raise NuGetError("индекс NuGet должен быть объектом JSON")
    resources = index.get("resources")
    if not isinstance(resources, list):
        raise NuGetError("в индексе NuGet отсутствует список resources")
    return find_package_base(resources)


def find_package_base(resources):
    """Проверяет ресурсы индекса и возвращает базовый HTTP(S)-адрес."""
    for resource in resources:
        if not isinstance(resource, dict):
            continue
        types = resource.get("@type")
        if isinstance(types, str):
            types = [types]
        if not isinstance(types, list) or PACKAGE_BASE_TYPE not in types:
            continue
        address = resource.get("@id")
        try:
            if not isinstance(address, str):
                raise ValueError("не задан строковый @id")
            return check_url(address).rstrip("/") + "/"
        except ValueError as error:
            raise NuGetError(f"неверный адрес PackageBaseAddress: {error}")
    raise NuGetError("в репозитории нет ресурса PackageBaseAddress/3.0.0")


def normalize_version(version):
    """Нормализует версию NuGet для URL; вход проверяется конфигурацией."""
    core, separator, suffix = version.split("+", 1)[0].partition("-")
    numbers = [part.lstrip("0") or "0" for part in core.split(".")]
    while len(numbers) < MIN_VERSION_PARTS:
        numbers.append("0")
    if len(numbers) == MAX_VERSION_PARTS and numbers[-1] == "0":
        numbers.pop()
    normalized = ".".join(numbers)
    if separator:
        normalized += "-" + suffix
    return normalized.lower()


def build_nuspec_url(base_address, package, version):
    """Строит URL манифеста только запрошенной версии пакета."""
    name = package.lower()
    normalized = normalize_version(version)
    return f"{base_address.rstrip('/')}/{name}/{normalized}/{name}.nuspec"


def read_metadata(data):
    """Разбирает XML .nuspec с пространством имён или без него."""
    try:
        root = ElementTree.fromstring(data)
    except ElementTree.ParseError as error:
        raise NuGetError(f"некорректный XML .nuspec: {error}") from error
    for element in root.iter():
        element.tag = element.tag.rsplit("}", 1)[-1]
    metadata = root.find("metadata")
    if root.tag != "package" or metadata is None:
        raise NuGetError("в .nuspec ожидаются элементы package и metadata")
    return metadata


def verify_identity(metadata, package, version):
    """Проверяет соответствие манифеста запрошенным имени и версии."""
    actual_package = metadata.findtext("id", "").strip()
    actual_version = metadata.findtext("version", "").strip()
    if actual_package.casefold() != package.casefold():
        raise NuGetError("имя пакета в .nuspec не совпадает с запрошенным")
    if not actual_version:
        raise NuGetError("в .nuspec отсутствует версия пакета")
    if normalize_version(actual_version) != normalize_version(version):
        raise NuGetError("версия в .nuspec не совпадает с запрошенной")


def read_dependency(element, framework):
    """Читает одну зависимость, сохраняя исходный диапазон её версий."""
    try:
        package = check_package(element.get("id", ""))
    except ValueError as error:
        raise NuGetError(f"неверное имя зависимости в .nuspec: {error}")
    version = element.get("version", "").strip()
    return Dependency(package, version, framework)


def parse_dependencies(data, package, version):
    """Извлекает все прямые зависимости из всех групп платформ .nuspec."""
    metadata = read_metadata(data)
    verify_identity(metadata, package, version)
    container = metadata.find("dependencies")
    if container is None:
        return []
    dependencies = []
    for element in container:
        if element.tag == "dependency":
            dependencies.append(read_dependency(element, ""))
        elif element.tag == "group":
            framework = element.get("targetFramework", "").strip()
            for child in element.findall("dependency"):
                dependencies.append(read_dependency(child, framework))
    return dependencies


def get_dependencies(repository, package, version):
    """Получает .nuspec указанной версии через индекс заданного репозитория."""
    base_address = get_package_base(repository)
    url = build_nuspec_url(base_address, package, version)
    return parse_dependencies(fetch_bytes(url), package, version)


def print_dependencies(package, version, dependencies):
    """Печатает прямые зависимости с диапазонами версий и платформами."""
    print(f"Прямые зависимости {package} {version}:")
    if not dependencies:
        print("Прямых зависимостей нет.")
        return
    for dependency in dependencies:
        framework = dependency.framework or "без указания платформы"
        constraint = dependency.version or "версия не ограничена"
        print(f"- {dependency.package} {constraint} [{framework}]")

"""Загрузка и проверка конфигурационного файла в формате YAML."""

import os
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import yaml

KEY_PACKAGE = "package"
KEY_REPOSITORY = "repository"
KEY_TEST_MODE = "test_mode"
KEY_VERSION = "version"
KEY_OUTPUT_IMAGE = "output_image"
KEY_ASCII_TREE = "ascii_tree"
KNOWN_KEYS = (
    KEY_PACKAGE,
    KEY_REPOSITORY,
    KEY_TEST_MODE,
    KEY_VERSION,
    KEY_OUTPUT_IMAGE,
    KEY_ASCII_TREE,
)

MAX_PACKAGE_ID_LENGTH = 100
PACKAGE_ID_PATTERN = re.compile(r"[A-Za-z0-9_]+(?:[.-][A-Za-z0-9_]+)*")
VERSION_PATTERN = re.compile(
    r"\d+(?:\.\d+){1,3}"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
)
URL_SCHEMES = ("http", "https")
IMAGE_SUFFIX = ".png"


class ConfigError(Exception):
    """Ошибка конфигурации; содержит список всех найденных проблем."""

    def __init__(self, problems):
        """Сохраняет список сообщений об ошибках."""
        super().__init__("; ".join(problems))
        self.problems = list(problems)


@dataclass(frozen=True)
class Config:
    """Проверенные параметры, заданные пользователем."""

    package: str
    repository: str
    test_mode: bool
    version: str
    output_image: str
    ascii_tree: bool

    def items(self):
        """Возвращает пары (ключ, значение) в порядке из конфига."""
        return [(key, getattr(self, key)) for key in KNOWN_KEYS]


def load_config(path):
    """Читает YAML-файл path и возвращает проверенный Config."""
    config_path = Path(path)
    raw = parse_yaml(read_text(config_path))
    problems = check_keys(raw)
    if problems:
        raise ConfigError(problems)
    values, problems = validate_values(raw, config_path.parent)
    if problems:
        raise ConfigError(problems)
    return Config(**values)


def read_text(config_path):
    """Возвращает текст конфигурационного файла."""
    if not config_path.is_file():
        raise ConfigError([f"файл конфигурации не найден: {config_path}"])
    try:
        return config_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise ConfigError(
            [f"не удалось прочитать {config_path}: {error}"]
        ) from error


def parse_yaml(text):
    """Разбирает YAML и проверяет, что корень является словарём."""
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as error:
        raise ConfigError([describe_yaml_error(error)]) from error
    if not isinstance(data, dict):
        raise ConfigError(
            ["корнем конфигурации должен быть словарь ключ: значение"]
        )
    return data


def describe_yaml_error(error):
    """Формирует краткое сообщение об ошибке разбора YAML."""
    mark = getattr(error, "problem_mark", None)
    problem = getattr(error, "problem", None) or str(error)
    if mark is None:
        return f"некорректный YAML: {problem}"
    return (
        f"некорректный YAML (строка {mark.line + 1}, "
        f"столбец {mark.column + 1}): {problem}"
    )


def check_keys(raw):
    """Сообщает об отсутствующих и неизвестных ключах."""
    problems = [
        f"не задан параметр '{key}'" for key in KNOWN_KEYS if key not in raw
    ]
    problems += [
        f"неизвестный параметр '{key}'"
        for key in raw
        if key not in KNOWN_KEYS
    ]
    return problems


def validate_values(raw, base_dir):
    """Проверяет все значения и возвращает (значения, ошибки)."""
    values = {}
    problems = []
    test_mode = raw[KEY_TEST_MODE]
    checks = [
        (KEY_PACKAGE, check_package, ()),
        (KEY_TEST_MODE, check_flag, ()),
        (KEY_REPOSITORY, check_repository, (test_mode, base_dir)),
        (KEY_VERSION, check_version, ()),
        (KEY_OUTPUT_IMAGE, check_output_image, ()),
        (KEY_ASCII_TREE, check_flag, ()),
    ]
    for key, check, extra in checks:
        try:
            values[key] = check(raw[key], *extra)
        except ValueError as error:
            problems.append(f"{key}: {error}")
    return values, problems


def require_text(value):
    """Проверяет, что value является непустой строкой, и обрезает её."""
    if not isinstance(value, str):
        raise ValueError(
            f"ожидается строка, получено {type(value).__name__} ({value!r})"
        )
    text = value.strip()
    if not text:
        raise ValueError("значение не должно быть пустым")
    return text


def check_package(value):
    """Проверяет имя пакета NuGet."""
    name = require_text(value)
    if len(name) > MAX_PACKAGE_ID_LENGTH:
        raise ValueError(
            f"имя длиннее {MAX_PACKAGE_ID_LENGTH} символов"
        )
    if not PACKAGE_ID_PATTERN.fullmatch(name):
        raise ValueError(
            f"'{name}' не является именем пакета NuGet "
            "(латиница, цифры, '_', '.', '-')"
        )
    return name


def check_flag(value):
    """Проверяет логический параметр (true или false)."""
    if not isinstance(value, bool):
        raise ValueError(f"ожидается true или false, получено {value!r}")
    return value


def check_repository(value, test_mode, base_dir):
    """Проверяет URL репозитория или путь к тестовому файлу."""
    location = require_text(value)
    if test_mode is True:
        return check_test_repository(location, base_dir)
    return check_url(location)


def check_url(location):
    """Проверяет, что location является URL с протоколом http(s)."""
    parsed = urlparse(location)
    if parsed.scheme not in URL_SCHEMES or not parsed.netloc:
        raise ValueError(
            f"'{location}' не является URL вида https://host/..."
        )
    return location


def check_test_repository(location, base_dir):
    """Проверяет путь к файлу тестового репозитория."""
    path = Path(location)
    if not path.is_absolute():
        path = Path(os.path.normpath(base_dir / path))
    if not path.is_file():
        raise ValueError(f"файл тестового репозитория не найден: {path}")
    return str(path)


def check_version(value):
    """Проверяет номер версии пакета в формате NuGet."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        raise ValueError(
            f"версия {value!r} прочитана как число; "
            "заключите её в кавычки, например \"8.0.0\""
        )
    version = require_text(value)
    if not VERSION_PATTERN.fullmatch(version):
        raise ValueError(
            f"'{version}' не похоже на версию NuGet "
            "(ожидается 1.2.3 или 1.2.3-beta)"
        )
    return version


def check_output_image(value):
    """Проверяет имя файла для изображения графа."""
    name = require_text(value)
    path = Path(name)
    if path.suffix.lower() != IMAGE_SUFFIX:
        raise ValueError(f"ожидается файл {IMAGE_SUFFIX}, получено '{name}'")
    if path.is_dir():
        raise ValueError(f"'{name}' является каталогом")
    if not path.parent.is_dir():
        raise ValueError(f"каталог '{path.parent}' не существует")
    return name

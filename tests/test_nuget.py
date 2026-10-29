"""Проверки получения прямых зависимостей NuGet без доступа к сети."""

import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import call, patch
from urllib.error import HTTPError, URLError

from src import main as app
from src import nuget

REPOSITORY = "https://example.org/v3/index.json"
BASE_ADDRESS = "https://content.example.org/packages/"
CONFIGS = Path(__file__).resolve().parent / "configs"
NAMESPACE = "http://schemas.microsoft.com/packaging/2013/05/nuspec.xsd"


def make_manifest(dependencies="", version="1.0.0", namespace=NAMESPACE):
    """Создаёт XML пакета A с заданными зависимостями и версией."""
    return (
        f'<package xmlns="{namespace}"><metadata>'
        f"<id>A</id><version>{version}</version>"
        f"{dependencies}</metadata></package>"
    ).encode("utf-8")


def run_main(config):
    """Возвращает код завершения, stdout и stderr консольного приложения."""
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = app.main([str(CONFIGS / config)])
    return code, out.getvalue(), err.getvalue()


class VersionTest(unittest.TestCase):
    """Выбор строго заданной версии и нормализация адреса манифеста."""

    def test_normalized_versions(self):
        """Учитываются нули, короткая версия, prerelease и build metadata."""
        cases = {
            "1.0": "1.0.0",
            "01.02.003.0": "1.2.3",
            "1.2.3.4": "1.2.3.4",
            "1.2.3-RC.1+build.2": "1.2.3-rc.1",
        }
        for value, expected in cases.items():
            with self.subTest(version=value):
                self.assertEqual(nuget.normalize_version(value), expected)

    def test_url_uses_requested_version(self):
        """URL содержит запрошенную версию, а не latest или чужую версию."""
        self.assertEqual(
            nuget.build_nuspec_url(BASE_ADDRESS, "Some.Package", "2.0"),
            BASE_ADDRESS + "some.package/2.0.0/some.package.nuspec",
        )


class ManifestTest(unittest.TestCase):
    """Разбор прямых зависимостей и контроль структуры манифеста."""

    def test_ungrouped_dependencies(self):
        """Читаются обычные зависимости, включая необязательную версию."""
        data = make_manifest(
            '<dependencies><dependency id="B" version="[1.0,2.0)" />'
            '<dependency id="C" /></dependencies>'
        )
        self.assertEqual(
            nuget.parse_dependencies(data, "A", "1.0.0"),
            [nuget.Dependency("B", "[1.0,2.0)", ""),
             nuget.Dependency("C", "", "")],
        )

    def test_all_frameworks_and_namespace_variants(self):
        """Сохраняются все платформы и их разные ограничения версий."""
        dependencies = (
            '<dependencies><group targetFramework="net8.0">'
            '<dependency id="B" version="8.0.0" /></group>'
            '<group targetFramework="netstandard2.0">'
            '<dependency id="B" version="[6.0,)" /></group>'
            '<group targetFramework="net9.0" /></dependencies>'
        )
        for namespace in (NAMESPACE, "", "urn:another:nuspec"):
            with self.subTest(namespace=namespace):
                result = nuget.parse_dependencies(
                    make_manifest(dependencies, namespace=namespace),
                    "a", "1.0.0.0",
                )
                self.assertEqual(
                    result,
                    [nuget.Dependency("B", "8.0.0", "net8.0"),
                     nuget.Dependency("B", "[6.0,)", "netstandard2.0")],
                )

    def test_no_dependencies(self):
        """Отсутствующие зависимости и пустые группы дают пустой список."""
        for text in ("", "<dependencies />",
                     '<dependencies><group targetFramework="net8.0" />'
                     '</dependencies>'):
            with self.subTest(xml=text):
                self.assertEqual(
                    nuget.parse_dependencies(make_manifest(text), "A", "1.0"),
                    [],
                )

    def test_malformed_manifest_is_rejected(self):
        """Ошибки XML, структуры, имени и версии не маскируются под успех."""
        cases = [
            b"not XML",
            b"<html><metadata /></html>",
            b"<package />",
            make_manifest().replace(b"<id>A</id>", b"<id>B</id>"),
            make_manifest(version="2.0.0"),
            make_manifest().replace(b"<version>1.0.0</version>", b""),
            make_manifest('<dependencies><dependency /></dependencies>'),
        ]
        for data in cases:
            with self.subTest(xml=data):
                with self.assertRaises(nuget.NuGetError):
                    nuget.parse_dependencies(data, "A", "1.0.0")


class RepositoryTest(unittest.TestCase):
    """Индекс репозитория, HTTP-загрузка и ошибки протокола."""

    def test_only_index_and_requested_manifest_are_fetched(self):
        """Зависимости не обходятся; адрес берётся из заданного индекса."""
        index = json.dumps({"resources": [
            {"@type": nuget.PACKAGE_BASE_TYPE, "@id": BASE_ADDRESS},
        ]}).encode()
        manifest = make_manifest(
            '<dependencies><dependency id="B" version="1.0" />'
            '</dependencies>', version="2.0.0",
        )
        with patch("src.nuget.urlopen", side_effect=[
            io.BytesIO(index), io.BytesIO(manifest),
        ]) as request:
            result = nuget.get_dependencies(REPOSITORY, "A", "2.0")
        self.assertEqual(result, [nuget.Dependency("B", "1.0", "")])
        self.assertEqual(request.call_args_list, [
            call(REPOSITORY, timeout=nuget.HTTP_TIMEOUT),
            call(BASE_ADDRESS + "a/2.0.0/a.nuspec",
                 timeout=nuget.HTTP_TIMEOUT),
        ])

    def test_invalid_service_indexes(self):
        """Неверные JSON и ресурсы индекса дают понятную ошибку."""
        cases = [
            b"not JSON", b"\xff", b"[]", b"{}",
            b'{"resources": {}}', b'{"resources": []}',
            b'{"resources": [null, 42]}',
            json.dumps({"resources": [
                {"@type": nuget.PACKAGE_BASE_TYPE, "@id": "file:///tmp"},
            ]}).encode(),
            json.dumps({"resources": [
                {"@type": nuget.PACKAGE_BASE_TYPE},
            ]}).encode(),
        ]
        for data in cases:
            with self.subTest(index=data):
                with patch("src.nuget.fetch_bytes", return_value=data):
                    with self.assertRaises(nuget.NuGetError):
                        nuget.get_package_base(REPOSITORY)

    def test_multiple_resource_types(self):
        """Поддерживается список типов ресурса и завершающий слеш адреса."""
        self.assertEqual(nuget.find_package_base([
            {"@type": ["Other", nuget.PACKAGE_BASE_TYPE],
             "@id": BASE_ADDRESS.rstrip("/")},
        ]), BASE_ADDRESS)

    def test_network_errors(self):
        """HTTP 404, HTTP 500, сетевые ошибки и таймаут обрабатываются."""
        cases = [
            HTTPError(REPOSITORY, 404, "Not Found", None, None),
            HTTPError(REPOSITORY, 500, "Server Error", None, None),
            URLError("connection failed"),
            TimeoutError("timed out"),
        ]
        for error in cases:
            with self.subTest(error=error):
                with patch("src.nuget.urlopen", side_effect=error):
                    with self.assertRaises(nuget.NuGetError) as context:
                        nuget.fetch_bytes(REPOSITORY)
                    self.assertIn(REPOSITORY, str(context.exception))


class MainTest(unittest.TestCase):
    """Консольный вывод второго этапа и коды завершения."""

    def test_dependencies_are_printed(self):
        """Выводятся зависимости с версиями и платформой."""
        with patch("src.main.get_dependencies", return_value=[
            nuget.Dependency("B", "[1.0,2.0)", "net8.0"),
        ]) as get_dependencies:
            code, out, err = run_main("valid.yaml")
        get_dependencies.assert_called_once_with(
            "https://api.nuget.org/v3/index.json", "Serilog", "3.1.1"
        )
        self.assertEqual(code, app.EXIT_SUCCESS)
        self.assertEqual(err, "")
        self.assertIn("- B [1.0,2.0) [net8.0]", out)
        self.assertNotIn("repository:", out)

    def test_empty_result(self):
        """Для пакета без зависимостей выводится явное сообщение."""
        with patch("src.main.get_dependencies", return_value=[]):
            code, out, err = run_main("valid.yaml")
        self.assertEqual(code, app.EXIT_SUCCESS)
        self.assertIn("Прямых зависимостей нет.", out)
        self.assertEqual(err, "")

    def test_default_dependency_labels(self):
        """Отсутствующие платформа и ограничение версии явно обозначаются."""
        out = io.StringIO()
        with redirect_stdout(out):
            nuget.print_dependencies("A", "1.0", [
                nuget.Dependency("B", "", ""),
            ])
        self.assertIn("B версия не ограничена", out.getvalue())
        self.assertIn("[без указания платформы]", out.getvalue())

    def test_data_error(self):
        """Сбой загрузки даёт код 2, сообщение в stderr и пустой stdout."""
        with patch("src.main.get_dependencies",
                   side_effect=nuget.NuGetError("HTTP 404")):
            code, out, err = run_main("valid.yaml")
        self.assertEqual(code, app.EXIT_DATA_ERROR)
        self.assertEqual(out, "")
        self.assertIn("HTTP 404", err)
        self.assertNotIn("Traceback", err)

    def test_test_graph_is_not_implemented_early(self):
        """Тестовый граф относится к этапу 3 и не запускает HTTP-загрузку."""
        with patch("src.main.get_dependencies") as get_dependencies:
            code, out, err = run_main("valid_test_mode.yaml")
        get_dependencies.assert_not_called()
        self.assertEqual(code, app.EXIT_DATA_ERROR)
        self.assertEqual(out, "")
        self.assertIn("этапом 3", err)


if __name__ == "__main__":
    unittest.main()

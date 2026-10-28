"""Тесты загрузки и проверки конфигурации (этап 1)."""

import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from src import main as app
from src.config import ConfigError, load_config

CONFIGS = Path(__file__).resolve().parent / "configs"
REPOS = Path(__file__).resolve().parent / "repos"


def run_app(name):
    """Запускает приложение с конфигом name, возвращает код и вывод."""
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = app.main([str(CONFIGS / name)])
    return code, out.getvalue(), err.getvalue()


class ValidConfigTest(unittest.TestCase):
    """Корректные конфигурации."""

    def test_real_repository(self):
        """Режим реального репозитория читается без ошибок."""
        config = load_config(CONFIGS / "valid.yaml")
        self.assertEqual(config.package, "Serilog")
        self.assertEqual(config.version, "3.1.1")
        self.assertFalse(config.test_mode)
        self.assertFalse(config.ascii_tree)

    def test_test_repository_path_is_relative_to_config(self):
        """Путь к тестовому файлу отсчитывается от каталога конфига."""
        config = load_config(CONFIGS / "valid_test_mode.yaml")
        self.assertTrue(config.test_mode)
        self.assertEqual(Path(config.repository), REPOS / "simple.txt")

    def test_prints_all_parameters(self):
        """Все шесть параметров печатаются в формате ключ: значение."""
        code, out, err = run_app("valid.yaml")
        self.assertEqual(code, app.EXIT_SUCCESS)
        self.assertEqual(err, "")
        self.assertEqual(
            out.splitlines(),
            [
                "package: Serilog",
                "repository: https://api.nuget.org/v3/index.json",
                "test_mode: false",
                "version: 3.1.1",
                "output_image: graph.png",
                "ascii_tree: false",
            ],
        )


class InvalidConfigTest(unittest.TestCase):
    """Обработка ошибок для каждого параметра."""

    CASES = {
        "no_such_config.yaml": "файл конфигурации не найден",
        "bad_syntax.yaml": "некорректный YAML",
        "not_mapping.yaml": "корнем конфигурации",
        "missing_keys.yaml": "не задан параметр 'repository'",
        "unknown_key.yaml": "неизвестный параметр 'depth'",
        "empty_package.yaml": "package: значение не должно быть пустым",
        "bad_package.yaml": "package: 'Serilog Sinks/Console'",
        "bad_url.yaml": "repository: 'api.nuget.org",
        "missing_repo_file.yaml": "файл тестового репозитория не найден",
        "bad_test_mode.yaml": "test_mode: ожидается true или false",
        "bad_version.yaml": "version: '3.x' не похоже на версию",
        "numeric_version.yaml": "прочитана как число",
        "bad_image.yaml": "output_image: ожидается файл .png",
        "bad_ascii_tree.yaml": "ascii_tree: ожидается true или false",
    }

    def test_each_error_is_reported(self):
        """Каждый сломанный конфиг даёт понятное сообщение и код 1."""
        for name, expected in self.CASES.items():
            with self.subTest(config=name):
                code, out, err = run_app(name)
                self.assertEqual(code, app.EXIT_CONFIG_ERROR)
                self.assertEqual(out, "")
                self.assertIn(expected, err)
                self.assertNotIn("Traceback", err)

    def test_all_problems_reported_at_once(self):
        """Ошибки во всех параметрах перечисляются за один запуск."""
        with self.assertRaises(ConfigError) as context:
            load_config(CONFIGS / "many_errors.yaml")
        keys = [p.split(":")[0] for p in context.exception.problems]
        self.assertEqual(
            keys,
            ["package", "repository", "version", "output_image", "ascii_tree"],
        )


if __name__ == "__main__":
    unittest.main()

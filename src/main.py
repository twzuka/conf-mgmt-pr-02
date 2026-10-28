"""Точка входа: инструмент визуализации графа зависимостей NuGet."""

import argparse
import sys

if __package__:
    from .config import ConfigError, load_config
else:
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from src.config import ConfigError, load_config

DEFAULT_CONFIG = "config.yaml"
EXIT_SUCCESS = 0
EXIT_CONFIG_ERROR = 1


def parse_args(argv):
    """Разбирает аргументы командной строки."""
    parser = argparse.ArgumentParser(
        description="Граф зависимостей пакетов NuGet."
    )
    parser.add_argument(
        "config",
        nargs="?",
        default=DEFAULT_CONFIG,
        help=f"путь к YAML-конфигурации (по умолчанию {DEFAULT_CONFIG})",
    )
    return parser.parse_args(argv)


def format_value(value):
    """Возвращает значение параметра в записи, принятой в YAML."""
    if isinstance(value, bool):
        return str(value).lower()
    return str(value)


def print_config(config):
    """Выводит параметры конфигурации в формате ключ: значение."""
    for key, value in config.items():
        print(f"{key}: {format_value(value)}")


def report_errors(error):
    """Печатает все ошибки конфигурации в stderr."""
    print("Ошибка конфигурации:", file=sys.stderr)
    for problem in error.problems:
        print(f"  - {problem}", file=sys.stderr)


def main(argv=None):
    """Запускает приложение и возвращает код завершения."""
    args = parse_args(argv)
    try:
        config = load_config(args.config)
    except ConfigError as error:
        report_errors(error)
        return EXIT_CONFIG_ERROR
    print_config(config)
    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(main())

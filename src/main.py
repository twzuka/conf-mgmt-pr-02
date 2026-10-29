"""Точка входа: инструмент визуализации графа зависимостей NuGet."""

import argparse
import sys

if __package__:
    from .config import ConfigError, load_config
    from .nuget import NuGetError, get_dependencies, print_dependencies
else:
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from src.config import ConfigError, load_config
    from src.nuget import NuGetError, get_dependencies, print_dependencies

DEFAULT_CONFIG = "config.yaml"
EXIT_SUCCESS = 0
EXIT_CONFIG_ERROR = 1
EXIT_DATA_ERROR = 2


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
    try:
        if config.test_mode:
            raise NuGetError(
                "чтение тестового графа предусмотрено этапом 3; "
                "для NuGet задайте test_mode: false"
            )
        dependencies = get_dependencies(
            config.repository, config.package, config.version
        )
    except NuGetError as error:
        print(f"Ошибка получения зависимостей: {error}", file=sys.stderr)
        return EXIT_DATA_ERROR
    print_dependencies(config.package, config.version, dependencies)
    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(main())

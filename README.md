# Граф зависимостей пакетов NuGet

Консольный инструмент для анализа зависимостей пакетов NuGet (.NET).
На втором этапе программа получает и выводит прямые зависимости конкретной
версии пакета. Готовые менеджеры пакетов и сторонние библиотеки для
получения зависимостей не используются.

Практическая работа № 2 по дисциплине «Конфигурационное управление».

- **Группа:** ИКБО-40-25.
- **Вариант:** 13.
- **Реализованы:** этап 1 — конфигурация; этап 2 — сбор прямых зависимостей.
- **Ветка:** `stage2`.
- [Первый этап](https://github.com/twzuka/conf-mgmt-pr-02/tree/stage1)
  сохранён отдельно в ветке `stage1`.

## Требования и запуск

- Python 3.9 или новее; Windows или Linux.
- Доступ по HTTP(S) к открытому репозиторию NuGet V3 и его ресурсу пакетов.
- PyYAML для чтения YAML-конфигурации. Получение и разбор зависимостей
  выполняются стандартной библиотекой Python: `urllib.request`, `json`
  и `xml.etree.ElementTree`.

Сборка не требуется. Все команды выполняются из корня репозитория.

### Windows (PowerShell)

```powershell
python -m pip install -r requirements.txt
.\run.bat config.yaml
```

### Linux

```bash
python3 -m pip install -r requirements.txt
./run.sh config.yaml
```

Без скрипта запуска: `python src/main.py config.yaml` в Windows
или `python3 src/main.py config.yaml` в Linux.

Единственный позиционный аргумент — путь к YAML-конфигурации.
По умолчанию используется `config.yaml` из текущего каталога.

## Настройки

Все шесть параметров обязательны; неизвестные параметры считаются ошибкой.

| Параметр | Тип | Назначение |
|---|---|---|
| `package` | строка | Имя анализируемого пакета |
| `repository` | строка | URL индекса NuGet V3 или путь к файлу тестового репозитория |
| `test_mode` | логическое | Выбор тестового репозитория; на этапе 2 необходимо `false` |
| `version` | строка | Конкретная версия анализируемого пакета |
| `output_image` | строка | Имя PNG-файла для этапа визуализации |
| `ascii_tree` | логическое | Включение ASCII-дерева на этапе визуализации |

```yaml
package: Microsoft.Extensions.Logging
repository: https://api.nuget.org/v3/index.json
test_mode: false
version: "8.0.0"
output_image: graph.png
ascii_tree: true
```

Правила проверки сохранены с первого этапа:

- `package` — непустая строка до 100 символов из латиницы, цифр, `_`,
  разделённых `.` или `-`.
- `repository` — при `test_mode: false` URL с протоколом `http` или
  `https`; при `test_mode: true` путь к существующему файлу.
  Относительный путь к тестовому файлу отсчитывается от каталога
  конфигурации.
- `version` — от двух до четырёх чисел через точку с необязательными
  суффиксами prerelease (`-метка`) и build metadata (`+метаданные`).
  Версию следует записывать в кавычках: YAML прочитает `3.1` без кавычек
  как число, и программа сообщит об ошибке.
- `output_image` — имя файла с расширением `.png`; его каталог должен
  существовать. Относительный путь проверяется от текущего каталога.
- `test_mode` и `ascii_tree` — только логические `true` или `false`.

Вывод всех настроек в формате «ключ — значение» относится только к первому
этапу. На втором этапе вместо него выводятся прямые зависимости.

Чтение файла тестового графа предусмотрено этапом 3. На этапе 2 при
`test_mode: true` проверяется конфигурация, затем выводится сообщение о
том, что чтение графа ещё не реализовано; сетевых запросов не выполняется.
Параметры `output_image` и `ascii_tree` проверяются, но пока не создают
изображение и дерево: визуализация предусмотрена этапом 5.

## Получение зависимостей

1. Загрузить JSON-индекс по адресу `repository`.
2. Найти в `resources` ресурс `PackageBaseAddress/3.0.0` и прочитать
   его `@id`. Адрес сервера пакетов не зашит в программу.
3. Привести имя пакета к нижнему регистру и нормализовать запрошенную
   версию: дополнить недостающую третью часть, убрать ведущие нули,
   нулевую четвёртую часть и build metadata; сохранить prerelease.
4. Загрузить XML-манифест по адресу
   `<base>/<package>/<version>/<package>.nuspec`.
5. Проверить, что имя и версия в манифесте соответствуют запросу.
6. Извлечь прямые элементы `dependency` из `dependencies`, включая
   элементы внутри всех групп `group`.
7. Вывести имя каждой зависимости, исходное ограничение версии и платформу
   из `targetFramework`.

Целевая платформа в задании и конфигурации не выбирается, поэтому выводятся
зависимости всех объявленных платформ. Одна зависимость может встречаться
несколько раз для разных платформ. Пустые группы не создают строк вывода.

Диапазон версии зависимости сохраняется без преобразования. Например,
`8.0.0` в метаданных зависимости означает нижнюю включённую границу,
а `[1.0,2.0)` — диапазон от 1.0 включительно до 2.0 исключительно.
Если версия не указана, печатается «версия не ограничена».
Платформа без `targetFramework` обозначается «без указания платформы».

Программа не подбирает версии зависимых пакетов и не загружает их
манифесты: транзитивный обход графа относится к этапу 3.
Если прямых зависимостей нет, выводится отдельное сообщение.

## Функции и методы исходного кода

| Модуль | Функция или метод | Назначение |
|---|---|---|
| `src/main.py` | `parse_args` | Разбор аргументов командной строки |
| | `report_errors` | Вывод ошибок конфигурации в stderr |
| | `main` | Загрузка конфигурации, получение и вывод зависимостей, код завершения |
| `src/config.py` | `ConfigError.__init__` | Сохранение списка проблем и сообщения исключения |
| | `Config.items` | Возврат всех пар «ключ — значение» в установленном порядке |
| | `load_config` | Чтение и проверка файла, возврат объекта `Config` |
| | `read_text` | Чтение UTF-8-файла конфигурации |
| | `parse_yaml` | Разбор YAML и проверка корневого словаря |
| | `describe_yaml_error` | Сообщение об ошибке YAML с доступной позицией |
| | `check_keys` | Поиск отсутствующих и неизвестных параметров |
| | `validate_values` | Проверка значений с накоплением ошибок |
| | `require_text` | Проверка непустой строки и удаление пробелов по краям |
| | `check_package` | Проверка имени пакета |
| | `check_flag` | Проверка логического значения |
| | `check_repository` | Выбор проверки URL или тестового файла |
| | `check_url` | Проверка протокола HTTP(S) и сетевой части URL |
| | `check_test_repository` | Проверка существования тестового файла |
| | `check_version` | Проверка синтаксиса версии пакета |
| | `check_output_image` | Проверка расширения PNG и каталога файла |
| `src/nuget.py` | `fetch_bytes` | HTTP(S)-загрузка с таймаутом 20 секунд и обработкой ошибок |
| | `get_package_base` | Разбор JSON-индекса и получение базового адреса пакетов |
| | `find_package_base` | Поиск и проверка ресурса `PackageBaseAddress/3.0.0` |
| | `normalize_version` | Нормализация номера версии для адреса NuGet |
| | `build_nuspec_url` | Построение URL манифеста заданной версии |
| | `read_metadata` | Разбор XML с пространством имён или без него |
| | `verify_identity` | Проверка имени и версии пакета в метаданных |
| | `read_dependency` | Чтение имени, ограничения версии и платформы одной зависимости |
| | `parse_dependencies` | Извлечение всех прямых зависимостей из манифеста |
| | `get_dependencies` | Последовательная загрузка индекса и нужного манифеста |
| | `print_dependencies` | Вывод списка зависимостей или сообщения об их отсутствии |

`Config` хранит проверенные настройки; `Dependency` — имя зависимости,
ограничение версии и платформу. `ConfigError` обозначает ошибку настроек,
а `NuGetError` — загрузки или разбора данных NuGet.

## Ошибки и коды завершения

| Код | Значение |
|---|---|
| `0` | Прямые зависимости получены, включая случай пустого списка |
| `1` | Ошибка чтения или проверки конфигурации |
| `2` | Ошибка данных NuGet, сети либо неподдерживаемый пока тестовый граф |

Неверные аргументы командной строки обрабатывает `argparse` с кодом `2`;
справка `--help` завершается с кодом `0`.

Ошибки выводятся в stderr. Для настроек сначала проверяется состав ключей,
затем значения. При корректном составе ключей найденные ошибки значений
перечисляются за один запуск.

Обрабатываются ошибки HTTP (в том числе отсутствие пакета или версии),
соединения и таймауты, некорректные JSON и XML, отсутствие нужного ресурса,
неверная структура манифеста, несовпадение имени или версии и неверное
имя зависимости.

## Примеры использования

Результат запуска с поставляемым `config.yaml`, полученный от NuGet:

```text
$ ./run.sh config.yaml
Прямые зависимости Microsoft.Extensions.Logging 8.0.0:
- Microsoft.Bcl.AsyncInterfaces 8.0.0 [.NETFramework4.6.2]
- Microsoft.Extensions.DependencyInjection 8.0.0 [.NETFramework4.6.2]
- Microsoft.Extensions.Logging.Abstractions 8.0.0 [.NETFramework4.6.2]
- Microsoft.Extensions.Options 8.0.0 [.NETFramework4.6.2]
- System.Diagnostics.DiagnosticSource 8.0.0 [.NETFramework4.6.2]
- System.ValueTuple 4.5.0 [.NETFramework4.6.2]
- Microsoft.Extensions.DependencyInjection 8.0.0 [net6.0]
- Microsoft.Extensions.Logging.Abstractions 8.0.0 [net6.0]
- Microsoft.Extensions.Options 8.0.0 [net6.0]
- Microsoft.Extensions.DependencyInjection 8.0.0 [net7.0]
- Microsoft.Extensions.Logging.Abstractions 8.0.0 [net7.0]
- Microsoft.Extensions.Options 8.0.0 [net7.0]
- Microsoft.Extensions.DependencyInjection 8.0.0 [net8.0]
- Microsoft.Extensions.Logging.Abstractions 8.0.0 [net8.0]
- Microsoft.Extensions.Options 8.0.0 [net8.0]
- Microsoft.Bcl.AsyncInterfaces 8.0.0 [.NETStandard2.0]
- Microsoft.Extensions.DependencyInjection 8.0.0 [.NETStandard2.0]
- Microsoft.Extensions.Logging.Abstractions 8.0.0 [.NETStandard2.0]
- Microsoft.Extensions.Options 8.0.0 [.NETStandard2.0]
- System.Diagnostics.DiagnosticSource 8.0.0 [.NETStandard2.0]
- Microsoft.Extensions.DependencyInjection 8.0.0 [.NETStandard2.1]
- Microsoft.Extensions.Logging.Abstractions 8.0.0 [.NETStandard2.1]
- Microsoft.Extensions.Options 8.0.0 [.NETStandard2.1]
- System.Diagnostics.DiagnosticSource 8.0.0 [.NETStandard2.1]
```

Для проверки пакета без зависимостей замените в `config.yaml` только
`package` на `Owin`, а `version` на `"1.0.0"` и повторите запуск.
Проверенный результат:

```text
Прямые зависимости Owin 1.0.0:
Прямых зависимостей нет.
```

При запросе `Microsoft.Extensions.Logging` версии `"9999.0.0"`
проверено сообщение «ресурс не найден (HTTP 404)» и код завершения `2`.

Ошибка конфигурации (файл входит в репозиторий):

```text
$ ./run.sh tests/configs/numeric_version.yaml
Ошибка конфигурации:
  - version: версия 3.1 прочитана как число; заключите её в кавычки, например "8.0.0"
```

## Тесты

Windows:

```powershell
python -m unittest discover -s tests -v
```

Linux:

```bash
python3 -m unittest discover -s tests -v
```

Автоматические тесты не требуют подключения к интернету: HTTP-ответы
подменяются через `unittest.mock`. Проверяются настройки, нормализация
версий, URL и количество запросов, все группы платформ, диапазоны версий,
отсутствие зависимостей, ошибки HTTP/сети/JSON/XML и консольный вывод.

Набор конфигураций для демонстрации ошибок находится в `tests/configs/`:

| Файл | Ошибка |
|---|---|
| `bad_syntax.yaml` | Синтаксическая ошибка YAML |
| `not_mapping.yaml` | Корень файла не словарь |
| `missing_keys.yaml` | Нет обязательных параметров |
| `unknown_key.yaml` | Неизвестный параметр |
| `empty_package.yaml`, `bad_package.yaml` | Пустое или недопустимое имя пакета |
| `bad_url.yaml` | URL без протокола |
| `missing_repo_file.yaml` | Отсутствующий тестовый файл |
| `bad_test_mode.yaml`, `bad_ascii_tree.yaml` | Не логическое значение |
| `bad_version.yaml`, `numeric_version.yaml` | Неверная версия или числовой тип |
| `bad_image.yaml` | Расширение файла не PNG |
| `many_errors.yaml` | Несколько ошибок значений |

Вспомогательные функции и проверки конфигурации:

| Функция или метод в `tests/test_config.py` | Назначение |
|---|---|
| `run_app` | Запуск CLI с перехватом вывода |
| `ValidConfigTest.test_real_repository` | Чтение корректных настроек |
| `ValidConfigTest.test_test_repository_path_is_relative_to_config` | Отсчёт пути от конфигурации |
| `ValidConfigTest.test_loads_all_parameters` | Сохранение шести параметров |
| `InvalidConfigTest.test_each_error_is_reported` | Ошибочные конфигурации |
| `InvalidConfigTest.test_all_problems_reported_at_once` | Накопление ошибок значений |

Проверки второго этапа:

| Функция или метод в `tests/test_nuget.py` | Назначение |
|---|---|
| `make_manifest` | Создание XML для тестов |
| `run_main` | Запуск CLI с перехватом вывода |
| `VersionTest.test_normalized_versions` | Нормализация версий |
| `VersionTest.test_url_uses_requested_version` | Версия в URL |
| `ManifestTest.test_ungrouped_dependencies` | Зависимости без групп |
| `ManifestTest.test_all_frameworks_and_namespace_variants` | Все платформы и XML-пространства имён |
| `ManifestTest.test_no_dependencies` | Пустые зависимости и группы |
| `ManifestTest.test_malformed_manifest_is_rejected` | Ошибки и несоответствие манифеста |
| `RepositoryTest.test_only_index_and_requested_manifest_are_fetched` | Только два необходимых запроса |
| `RepositoryTest.test_invalid_service_indexes` | Неверные индексы |
| `RepositoryTest.test_multiple_resource_types` | Несколько типов ресурса |
| `RepositoryTest.test_network_errors` | HTTP, соединение и таймаут |
| `MainTest.test_dependencies_are_printed` | Вывод зависимостей |
| `MainTest.test_empty_result` | Сообщение о пустом результате |
| `MainTest.test_default_dependency_labels` | Метки отсутствующих версии и платформы |
| `MainTest.test_data_error` | Ошибка загрузки в CLI |
| `MainTest.test_test_graph_is_not_implemented_early` | Граница этапов 2 и 3 |

При проверке этапа прошли 20 тестов на Python 3.12 (Linux).
Реальные запросы проверены для `Microsoft.Extensions.Logging` 7.0.0 и
8.0.0, `Owin` 1.0.0 и отсутствующей версии пакета.
Запуск на Windows отдельно не проверялся.

## Структура репозитория

| Путь | Назначение |
|---|---|
| `src/config.py` | Чтение и проверка настроек |
| `src/nuget.py` | Сбор прямых зависимостей |
| `src/main.py` | Консольный интерфейс |
| `tests/test_config.py` | Проверки конфигурации |
| `tests/test_nuget.py` | Проверки второго этапа |
| `tests/configs/` | Корректные и ошибочные настройки |
| `tests/repos/` | Файл для проверки пути тестового репозитория |
| `config.yaml` | Пример настроек |
| `requirements.txt` | Зависимость для чтения YAML |
| `run.sh`, `run.bat` | Скрипты запуска |
| `.gitignore` | Исключение служебных и сгенерированных файлов |

## Документация формата NuGet

- [NuGet V3: Package Content](https://learn.microsoft.com/en-us/nuget/api/package-base-address-resource).
- [.nuspec: зависимости](https://learn.microsoft.com/en-us/nuget/reference/nuspec#dependencies).
- [Нормализация версий](https://learn.microsoft.com/en-us/nuget/concepts/package-versioning#normalized-version-numbers).

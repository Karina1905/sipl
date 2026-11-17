# SIPL Toolkit

[![CI](https://github.com/Karina1905/sipl/actions/workflows/ci.yml/badge.svg)](https://github.com/Karina1905/sipl/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/Karina1905/sipl)](https://github.com/Karina1905/sipl/releases)
[![PyPI](https://img.shields.io/pypi/v/sipl-lang-toolkit)](https://pypi.org/project/sipl-lang-toolkit/)

Курсовий проєкт з дисципліни «Теорія програмування». Інструменти для мови SIPL:
граматика, парсер з AST, інтерпретатор з trace, CLI, conformance-тести, візуалізація
дерева виводу та AST.

## Обрані завдання

| ID | Завдання | Бали |
|---|---|---|
| CORE-01 | Формальна специфікація SIPL | 0.5 |
| CORE-02 | Парсер та типізоване AST з SourceSpan | 1.5 |
| CORE-03 | Інтерпретатор SIPL | 2.0 |
| CORE-04 | Подієва модель виконання та trace | 1.0 |
| CORE-05 | CLI: parse, check, run, trace + JSON | 1.0 |
| CORE-06 | Conformance suite | 1.0 |
| VIS-01 | Візуалізація дерева синтаксичного виводу | 1.5 |
| VIS-02 | Візуалізація AST та порівняння Parse Tree ↔ AST | 1.0 |
| REL-01 | CI | 0.5 |
| REL-02 | GitHub Releases + SemVer + CHANGELOG | 0.5 |
| REL-03 | Публікація пакета в PyPI | 0.5 |
| | **Разом** | **11.0** |

Де що реалізовано:

- CORE-01: `grammar/sipl.ebnf`, `src/sipl/grammar/sipl.lark`, `examples/`, `tests/test_grammar.py`
- CORE-02: `src/sipl/parser.py`, `src/sipl/ast.py`, `src/sipl/diagnostics.py`
- CORE-03, CORE-04: `src/sipl/interpreter/`
- CORE-05: `src/sipl/cli.py`, `docs/cli.md`, `tests/test_cli.py`
- CORE-06: `conformance/`, `docs/conformance.md`
- VIS-01, VIS-02: `src/sipl/visualization/`
- REL-01..03: `.github/workflows/`, `CHANGELOG.md`, `docs/publishing.md`

## Встановлення

Потрібен Python 3.10+.

З PyPI:

```bash
pip install sipl-lang-toolkit
```

З репозиторію:

```bash
git clone https://github.com/Karina1905/sipl.git
cd sipl
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## Використання

```bash
sipl check examples/valid/power.sipl                     # перевірка синтаксису
sipl parse examples/valid/power.sipl                     # AST
sipl run   examples/valid/power.sipl -s X=2 -s Y=10      # виконання
sipl trace examples/valid/power.sipl -s X=2 -s Y=2       # покрокове виконання
sipl run   examples/valid/power.sipl --input '{"X": 2, "Y": 10}' --json
```

Візуалізація:

```bash
sipl tree examples/valid/power.sipl --kind parse --rules            # дерево виводу з правилами БНФ
sipl tree examples/valid/power.sipl --kind ast --format svg -o ast.svg
sipl tree examples/valid/power.sipl --kind both --format svg -o compare.svg
```

- `--format`: `text`, `json`, `dot`, `svg`.
- `--compact`: дерево виводу без ланцюжків одиничних правил.
- У SVG при наведенні на вузол видно його позицію і фрагмент коду.

Коди завершення: `0` успіх, `1` синтаксична помилка, `2` неправильні аргументи,
`3` помилка виконання, `4` ліміт кроків, `5` файл не знайдено. Формат JSON — у `docs/cli.md`.

Приклад:

```
$ sipl run examples/valid/power.sipl -s X=2 -s Y=10
X = 2
Y = 0
R = 1024

$ sipl check examples/invalid/less_than_not_in_sipl.sipl
examples/invalid/less_than_not_in_sipl.sipl:2:11: syntax error: unexpected character '<'
     2 |   while X < 10 do X := X + 1
       |           ^
  hint: SIPL has only '=' and '>' comparisons: write 'Y > X' instead of 'X < Y'
```

## Мова

Граматика відповідає БНФ з практикуму (ПР 1):

```
P ::= begin S end
S ::= x := a | S1 ; S2 | if b then S1 else S2 | while b do S | begin S end | skip
a ::= n | x | a1 + a2 | a1 - a2 | a1 * a2 | (a)
b ::= a1 = a2 | a1 > a2 | b1 ∨ b2 | ¬b | (b)
```

- `∨` / `¬` можна писати як `or` / `not`.
- Пріоритети: `*` вище за `+ -`, `¬` вище за `∨`, бінарні операції лівоасоціативні.
- then-гілка може бути послідовністю, else-гілка і тіло `while` — один оператор.
- `n` — ціле число, може бути від'ємним (`-5`).
- Коментарі `//` і `/* */` дозволені, у дерево виводу не потрапляють.

Повна граматика з номерами правил — `grammar/sipl.ebnf`.

## Тести

```bash
pytest --cov=sipl                            # 263 тести, покриття ~96%
ruff check . && mypy                         # lint і типи
python conformance/run_conformance.py -v     # conformance suite (33 кейси)
```

Conformance suite не імпортує пакет, а запускає будь-яку реалізацію через CLI:
`python conformance/run_conformance.py --impl "<команда>"`.

## CI і релізи

- `ci.yml` — на кожен push/PR: ruff, mypy, pytest (Python 3.10–3.14), conformance, збірка
  wheel/sdist і перевірка встановлення в чистому venv.
- `release.yml` — на тег `vX.Y.Z`: перевірка версії, збірка, публікація в PyPI,
  перевірка встановлення з PyPI, GitHub Release з артефактами та нотатками з `CHANGELOG.md`.

Налаштування PyPI — `docs/publishing.md`.

## Структура

```
grammar/            EBNF-специфікація
src/sipl/
  grammar/          граматика Lark
  parser.py         текст → дерево виводу → AST
  ast.py            вузли AST
  diagnostics.py    SourceSpan, помилки
  interpreter/      виконання, події trace
  visualization/    text / JSON / DOT / SVG
  cli.py
examples/           13 коректних і 19 некоректних програм
conformance/        кейси і раннер
tests/
docs/               cli.md, conformance.md, architecture.md, publishing.md, defense.md
```

## Обмеження

- Тільки цілі числа, булеві значення є лише в умовах.
- Немає ділення, `<`, `and`, `true/false` — їх немає в БНФ курсу.
- Читання невизначеної змінної — помилка виконання.
- Нескінченні цикли зупиняються лімітом кроків (за замовчуванням 100 000, `--max-steps`).
- Без процедур і рекурсивних функцій.

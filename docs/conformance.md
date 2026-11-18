# Conformance suite SIPL

Набір програм з очікуваною поведінкою, який можна запустити проти **будь-якої**
реалізації SIPL — не лише проти цієї. Раннер `conformance/run_conformance.py`
використовує лише стандартну бібліотеку Python і спілкується з реалізацією виключно
через командний рядок і JSON (`docs/cli.md`).

```bash
python conformance/run_conformance.py                          # реалізація `sipl` з PATH
python conformance/run_conformance.py --impl "python -m sipl"  # будь-яка команда
python conformance/run_conformance.py --impl "node my-sipl.js" -v
python conformance/run_conformance.py -k 10                    # фільтр за назвою
python conformance/run_conformance.py --ignore-spans           # AST без позицій
```

Код завершення: `0` — всі кейси пройдено, `1` — є провали, `2` — кейсів не знайдено.

## Вимоги до реалізації

Реалізація має підтримувати дві команди:

```
<impl> run --json --input '<JSON-стан>' [--max-steps N] FILE
<impl> parse --json FILE
```

`run` завершується кодом `0` (ok), `1` (syntax_error), `3` (runtime_error) або
`4` (step_limit) і друкує JSON з полями `status` (`ok | syntax_error | runtime_error | step_limit`),
`state` (кінцевий стан або стан у момент помилки) та діагностикою в
`diagnostic` або `diagnostics[0]` з `span.line`, `span.column`, `message`.
`parse` друкує JSON з полем `ast` у форматі з `docs/cli.md`.

## Формат кейсу

Кожен кейс — пара файлів у `conformance/cases/`:

- `NNN_name.sipl` — програма;
- `NNN_name.json` — очікування;
- (необов'язково) `NNN_name.ast.json` — еталонне AST.

```json
{
  "description": "Читання невизначеної змінної",
  "input": {"x": 1},
  "max_steps": 1000,
  "expect": {
    "status": "runtime_error",
    "state": {"x": 1},
    "error": {"line": 2, "column": 6, "message_contains": "undefined"},
    "ast": "101_undefined_var.ast.json"
  }
}
```

| Поле | Обов'язкове | Перевірка |
|---|---|---|
| `description` | так | — |
| `input` | ні (типово `{}`) | початковий стан |
| `max_steps` | ні | передається як `--max-steps` |
| `expect.status` | так | точна рівність; також перевіряється код завершення |
| `expect.exit_code` | ні | інший очікуваний код завершення (типово — за `status`) |
| `expect.state` | ні | точна рівність словника станів |
| `expect.error.line/column` | ні | позиція першої діагностики |
| `expect.error.message_contains` | ні | підрядок повідомлення |
| `expect.ast` | ні | рівність AST (поле `id` ігнорується; `span` — з `--ignore-spans`) |

Нумерація: `0xx` — коректне виконання, `1xx` — помилки виконання, `2xx` — синтаксичні
помилки.

`--bless` перезаписує файли `*.ast.json` за поточною реалізацією — використовуйте лише
після ручної перевірки AST (`sipl parse FILE`).

## Покриття

33 кейси: усі правила БНФ (P1, S1–S6, A1–A6, B1–B5), пріоритет і асоціативність,
від'ємні числові літерали, `∨`/`¬` та `or`/`not`, межі then/else/while, коментарі,
невизначені змінні, ліміт кроків, 13 синтаксичних помилок з позиціями — зокрема
конструкції, яких немає в SIPL (`/`, `<`, `and`, `true`, `-X`, програма без `begin…end`).

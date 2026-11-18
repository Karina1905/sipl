# CLI `sipl`

```
sipl parse   FILE [--json] [--no-spans]          AST програми
sipl check   FILE [--json]                       синтаксична перевірка
sipl run     FILE [-s X=1 ...] [--input JSON] [--max-steps N] [--json]
sipl trace   FILE [-s X=1 ...] [--input JSON] [--max-steps N] [--format text|json|jsonl] [-v]
sipl tree    FILE [--kind parse|ast|both] [--rules] [--compact] [--format text|json|dot|svg] [-o OUT] [--no-spans]
sipl grammar                                     вивести граматику Lark
```

`FILE` може бути `-` (stdin). Початковий стан: `-s NAME=INT` (можна повторювати) та/або
`--input '{"X": 2}'` (JSON-рядок або шлях до JSON-файлу); `-s` перекриває `--input`.

## Коди завершення (стабільні)

| Код | Значення |
|---|---|
| 0 | успіх |
| 1 | синтаксична помилка |
| 2 | помилка використання: невідома команда/опція, некоректний `--set`/`--input`, `--max-steps <= 0` |
| 3 | помилка виконання (читання невизначеної змінної) |
| 4 | перевищено ліміт кроків |
| 5 | помилка вводу-виводу (файл не знайдено) |

## JSON-контракт (`schema_version: 1`)

Кожна команда з `--json` друкує один JSON-об'єкт з обов'язковими полями:

```json
{ "schema_version": 1, "command": "run", "file": "power.sipl", "ok": true, ... }
```

### Успіх

| Команда | Додаткові поля |
|---|---|
| `parse` | `ast` — дерево AST (див. нижче) |
| `check` | `diagnostics: []`, `variables: ["R", "Y", "X"]` |
| `run` | `input`, `status`, `state`, `steps`, `diagnostic?` |
| `trace` | як `run` + `trace: [Event, ...]` |

`status` ∈ `ok | runtime_error | step_limit`; для них `ok == (status == "ok")`.

### Помилка до виконання (синтаксис, ввід)

```json
{ "schema_version": 1, "command": "check", "file": "bad.sipl", "ok": false,
  "status": "syntax_error",
  "diagnostics": [ { "kind": "syntax_error", "message": "unexpected '='; expected ':='",
                     "span": {"line":2,"column":5,"end_line":2,"end_column":6,"start":10,"end":11},
                     "hint": "use ':=' for assignment, '=' is comparison",
                     "expected": ["':='"] } ] }
```

`status` тут ∈ `syntax_error | input_error | io_error`.

### Diagnostic

`{kind, message, span?, hint?, ...}`; `kind` ∈ `syntax_error | runtime_error | step_limit |
input_error | io_error`.

### SourceSpan

`{line, column, end_line, end_column, start, end}` — рядки/колонки з 1, кінець
не включається; `start`/`end` — зміщення з 0.

### AST-вузол

```json
{ "type": "Assign", "id": 3, "target": "R",
  "expr": { "type": "Num", "id": 4, "value": 1, "span": {...} },
  "span": {...} }
```

| type | поля |
|---|---|
| `Program` | `body` |
| `Seq` | `statements: [...]` |
| `Assign` | `target`, `expr` |
| `If` | `cond`, `then_branch`, `else_branch` |
| `While` | `cond`, `body` |
| `Block` | `body` |
| `Skip` | — |
| `Num` / `Var` | `value` (ціле, може бути від'ємним) / `name` |
| `BinOp` | `op` ∈ `+ - *`, `left`, `right` |
| `Compare` | `op` ∈ `= >`, `left`, `right` |
| `BoolOp` | `op` = `or` (∨), `left`, `right` |
| `Not` | `operand` (¬) |

`Program.body` — тіло `S` з правила `P ::= begin S end` (зовнішні `begin`/`end` належать
програмі, тому окремого вузла `Block` для них немає).

`id` — номер вузла в обході в прямому порядку (pre-order) від 0.

### Події trace

Усі мають `event` і `step` (кількість розпочатих операторів):

| event | поля |
|---|---|
| `ProgramStarted` | `state` |
| `BeforeStatement` | `node_id`, `kind`, `span`, `state` (стан *до*) |
| `VariableChanged` | `node_id`, `name`, `old` (`null` = була невизначена), `new`, `span` |
| `ConditionEvaluated` | `node_id` (if/while), `cond_id`, `construct` (`if`/`while`), `value`, `span`, `iteration` |
| `AfterStatement` | `node_id`, `kind`, `span`, `state` (стан *після*) |
| `ProgramFinished` | `status`, `state`, `diagnostic` |

`--format jsonl` — по одній події на рядок (зручно для потокової обробки).

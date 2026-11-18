# Архітектура SIPL Toolkit

```
             ┌──────────────── src/sipl ────────────────────────────────────────┐
source text  │  parser.py                                                        │
───────────► │   Lark (LALR, sipl.lark) ─► ParseNode  ─► _AstBuilder ─► ast.Program│
             │                       (дерево виводу)        (типізоване AST)     │
             │                              │                     │              │
             │  visualization/              ▼                     ▼              │
             │   tree_view.py   from_parse_tree()          from_ast()            │
             │   exporters.py   to_text / to_json / to_dot / to_svg              │
             │                                                    │              │
             │  interpreter/machine.py   Interpreter.events() ◄───┘              │
             │      генератор подій ──► events.py (BeforeStatement, ...)         │
             │      run() / trace()  ──► ExecutionResult                         │
             │                                                                   │
             │  cli.py   parse | check | run | trace | tree | grammar            │
             └───────────────────────────────────────────────────────────────────┘
conformance/run_conformance.py — незалежний від реалізації прогін через CLI/JSON
```

## Шари і контракти

| Шар | Модуль | Вхід → вихід | Контракт |
|---|---|---|---|
| Граматика | `src/sipl/grammar/sipl.lark`, `grammar/sipl.ebnf` | — | версія мови 1.0 |
| Лексер + парсер | `parser.parse_tree()` | `str` → `ParseNode` | кожен вузол має `SourceSpan` і `node_id` |
| Побудова AST | `parser.parse()` | `ParseNode` → `ast.Program` | власні dataclass-вузли, без типів Lark |
| Діагностика | `diagnostics.py` | — | `Diagnostic(kind, message, span, hint)` → `to_dict()` |
| Виконання | `interpreter.Interpreter.events()` | `Program` + стан → потік подій | `Event.to_dict()` |
| CLI | `cli.py` | файли → текст/JSON | `docs/cli.md`, `schema_version: 1` |
| Візуалізація | `visualization/` | `ParseNode`/`AST` → text/JSON/DOT/SVG/HTML | `TreeView.to_dict()` |

### Чому дерево виводу і AST — різні структури

Граматика навмисно записана **без** інлайнінгу правил Lark (`?rule`), а парсер
запускається з `keep_all_tokens=True`. Тому Lark повертає повне дерево виводу за БНФ:
з ланцюжками `<arith expr> → <term> → <factor>`, ключовими словами й розділювачами.
Воно одразу конвертується у власний `ParseNode` (VIS-01), а `_AstBuilder` будує з нього
AST: відкидає пунктуацію та ланцюгові правила, дужки зберігаються лише як span виразу,
композиція `S1 ; S2 ; S3` сплющується в `Seq(statements=...)` (композиція асоціативна).
Для `power.sipl` це 65 вузлів дерева виводу проти 18 вузлів AST.

### SourceSpan

`line`/`column` — 1-based, `end_*` — позиція *після* останнього символу, `start`/`end` —
0-based зміщення в тексті (`source[start:end]` дає фрагмент). Спани є в кожному вузлі
дерева виводу, AST, у подіях виконання та в діагностиці.

### Інтерпретатор як генератор подій

`Interpreter.events()` — генератор Python. Кожна дія (початок/кінець оператора, зміна
змінної, перевірка умови) віддається як подія *до* продовження виконання. Отже,
налагоджувач може зупинитися, просто не беручи наступну подію (тест
`test_interpreter_is_lazy`). Події містять `node_id` і `span`, тож їх можна пов'язати
з AST і текстом.

Захист від нескінченних циклів: лічильник кроків (кожен оператор, крім `Seq`, — один
крок); при перевищенні `max_steps` виконання завершується зі статусом `step_limit`.

Невизначеність (часткова семантика) моделюється явно: читання відсутньої змінної дає
`runtime_error` з SourceSpan і станом на момент помилки.

## Межі реалізації

- Граматика рівно за БНФ курсу (`P ::= begin S end`; `+ - *`; `= >`; `∨ ¬`); конструкції
  поза БНФ (`/`, `<`, `and`, `true`…) відхиляються парсером з підказкою.
- Неоднозначності БНФ розв'язано як у Pascal (див. коментарі в `grammar/sipl.ebnf`).
- Лише цілі числа; булеві значення існують тільки в умовах; без процедур/функцій.
- Повідомлення про синтаксичні помилки — англійською (стабільні для тестів), підказки
  `hint` пояснюють типові помилки (`=` замість `:=`, зайва `;`, відсутній `else`...).

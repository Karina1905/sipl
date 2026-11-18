# Changelog

Формат — [Keep a Changelog](https://keepachangelog.com/uk/1.1.0/),
версіонування — [SemVer](https://semver.org/lang/uk/). Номери версій відповідають
рекомендованому циклу курсового проєкту (0.1 синтаксис → 0.4 візуалізація).

## [Unreleased]

## [0.4.0] — 2026-11-17

Перший публічний реліз модулів ядра та візуалізації (етапи 0.1–0.4 roadmap).

### Added
- **Граматика (CORE-01):** машинозчитувана граматика Lark `src/sipl/grammar/sipl.lark`
  та EBNF `grammar/sipl.ebnf`, що точно відповідають БНФ курсу (P1, S1–S6, A1–A6, B1–B5);
  13 коректних і 19 некоректних прикладів у `examples/`, плюс 15/24 тестових фрагментів.
- **Парсер та AST (CORE-02):** власні вузли AST (dataclass) з `SourceSpan` і `node_id`;
  конкретне дерево виводу `ParseNode`; діагностики з рядком/колонкою, переліком
  очікуваних токенів і підказками; серіалізація AST у JSON та назад.
- **Інтерпретатор (CORE-03):** присвоювання, композиція, if, while, begin/end, skip;
  цілочисельна арифметика `+ - *`, порівняння `= >`, `∨`/`¬` (або `or`/`not`);
  невизначені змінні як помилки виконання; ліміт кроків проти нескінченних циклів.
- **Trace (CORE-04):** подієва модель `ProgramStarted`, `BeforeStatement`,
  `VariableChanged`, `ConditionEvaluated`, `AfterStatement`, `ProgramFinished`;
  інтерпретатор-генератор, придатний для покрокового налагодження.
- **CLI (CORE-05):** `sipl parse | check | run | trace | tree | grammar`,
  JSON-режим зі `schema_version: 1`, стабільні коди завершення.
- **Conformance suite (CORE-06):** 33 кейси і незалежний раннер на stdlib; перевіряє
  статус, стан, позицію помилки, AST і код завершення.
- **Візуалізація дерева виводу (VIS-01):** text / JSON / DOT / SVG, вузли пов'язані
  з фрагментами коду; компактний режим `--compact` (без ланцюжків одиничних правил) і
  `--kind both` — обидва дерева на одній картинці; `--rules` — номер правила БНФ
  (P1, S1–S6, A1–A6, B1–B5) біля кожного вузла.
- **Візуалізація AST (VIS-02):** text / JSON / DOT / SVG; `sipl tree --kind both` — дерево
  виводу й AST поруч на одній SVG-картинці.
- **CI (REL-01):** GitHub Actions — ruff, mypy, pytest з покриттям ≥ 80 %,
  conformance, збірка wheel/sdist і перевірка в чистому venv.
- **Release (REL-02):** workflow релізу за тегом `v*.*.*` з перевіркою версії,
  release notes з цього файлу та артефактами збірки.
- **PyPI (REL-03):** пакет `sipl-lang-toolkit` публікується в PyPI через Trusted
  Publishing; після публікації workflow встановлює його в чистому середовищі й
  перевіряє, що версія відповідає тегу.

[Unreleased]: https://github.com/Karina1905/sipl/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/Karina1905/sipl/releases/tag/v0.4.0

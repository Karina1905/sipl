# Публікація в PyPI (REL-03)

Пакет: **`sipl-lang-toolkit`** (модуль і команда — `sipl`). Публікацію виконує workflow
`.github/workflows/release.yml` за тегом `vX.Y.Z` через
[Trusted Publishing](https://docs.pypi.org/trusted-publishers/): GitHub Actions отримує
короткоживучий OIDC-токен, тож жодних API-ключів у репозиторії чи секретах немає.

## Одноразове налаштування

1. Зареєструватися на https://pypi.org і ввімкнути 2FA (обов'язково для публікації).
2. Відкрити **Your account → Publishing → Add a new pending publisher** і заповнити:

   | Поле | Значення |
   |---|---|
   | PyPI Project Name | `sipl-lang-toolkit` |
   | Owner | ваш логін GitHub |
   | Repository name | `sipl` (або як названо репозиторій) |
   | Workflow name | `release.yml` |
   | Environment name | `pypi` |

3. У репозиторії на GitHub: **Settings → Environments → New environment** → `pypi`.

## Випуск версії

```bash
# версія вже 0.4.0 у pyproject.toml, src/sipl/__init__.py і CHANGELOG.md
git push origin main
git push origin v0.4.0
```

Workflow: тести → збірка → **публікація в PyPI** → встановлення з PyPI в чистому venv
з перевіркою `sipl --version == тег` → GitHub Release.

Тег і версія мусять збігатися — інакше перший крок зупинить реліз. PyPI не дозволяє
повторно завантажити ту саму версію, тож для виправлень підвищуйте patch-версію
(`0.4.1`): оновіть `pyproject.toml`, `src/sipl/__init__.py`, додайте розділ у
`CHANGELOG.md`, створіть тег `v0.4.1`.

## Перевірка в чистому середовищі

```bash
python -m venv /tmp/check && /tmp/check/bin/pip install sipl-lang-toolkit
/tmp/check/bin/sipl --version                        # sipl 0.4.0
# або через uv:
uv run --with sipl-lang-toolkit --no-project -- sipl --version
```

## Ручна публікація (запасний варіант)

Якщо Actions недоступні: створіть API-токен на PyPI (scope — проєкт) і виконайте

```bash
python -m build
python -m twine upload dist/*        # логін: __token__, пароль: токен
```

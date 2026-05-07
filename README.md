# G-Market Azeroth

Минимальный скелет Telegram-бота для проекта G-Market Azeroth.

## Что внутри

- `src/g_market_azeroth` - код Telegram-бота.
- `Dockerfile` и `docker-compose.yml` - запуск на сервере.
- `.env.example` - пример переменных окружения.
- `.github/workflows/ci.yml` - базовая проверка проекта в GitHub Actions.

Сейчас бот умеет отвечать на `/start` сообщением:

```text
Привет!
```

## Локальный запуск

1. Создайте бота через BotFather и получите токен.
2. Скопируйте файл окружения:

```bash
cp .env.example .env
```

3. Укажите токен в `.env`:

```env
BOT_TOKEN=123456789:your_real_token
```

4. Установите зависимости и запустите бота:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m g_market_azeroth
```

На Windows PowerShell активация окружения выглядит так:

```powershell
.venv\Scripts\Activate.ps1
```

## Запуск через Docker Compose

```bash
cp .env.example .env
docker compose up -d --build
```

Логи:

```bash
docker compose logs -f bot
```

Остановка:

```bash
docker compose down
```

## Деплой на Timeweb Cloud

Подойдёт обычный VPS с Ubuntu и установленными Docker + Docker Compose.

1. Создайте репозиторий на GitHub и отправьте туда код.
2. На сервере клонируйте репозиторий:

```bash
git clone https://github.com/<user>/<repo>.git g-market-azeroth
cd g-market-azeroth
```

3. Создайте `.env` и укажите `BOT_TOKEN`.
4. Запустите контейнер:

```bash
docker compose up -d --build
```

После этого бот будет работать через long polling, отдельный домен и webhook пока не нужны.

## Backend Architecture

The bot is organized as a small layered backend:

```text
handlers
-> services
-> repositories
-> database facade
```

- `handlers.py` and `admin.py` own Telegram commands, callbacks, FSM transitions, and user/admin messages.
- `services/` contains focused business helpers, including product validation and request status formatting.
- `repositories/` contains SQLite query code for clients, products, purchase/sell requests, and support tickets.
- `database.py` is the facade used by handlers; it initializes schemas and delegates database work to repositories.
- CI runs source compilation and the pytest suite in GitHub Actions.
- Tests currently cover configuration loading and error handlers.
- Anti-spam is implemented by the rate-limit middleware and configurable cooldown settings.
- Logging is initialized centrally in `logging.py`; audit logs record key user/admin actions and metric logs record lightweight analytics events.
- `healthcheck.py` validates config, `BOT_TOKEN`, SQLite connectivity, and `SELECT 1` without calling Telegram.
- `backup.py` creates timestamped SQLite backups in `backups/` and keeps the latest 10 files.

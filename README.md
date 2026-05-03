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

# Steam SMM Telegram Bot

Telegram бот для автоматической накрутки в Steam с интегрированными платёжными системами.

## 🚀 Возможности

### Накрутка Steam
- 💬 **Комментарии** — накрутка комментариев на профиле Steam
- 👍 **Лайки** — накрутка лайков на скриншоты и иллюстрации
- 👥 **Подписки** — накрутка подписчиков в группы Steam
- ⭐ **Обзоры** — накрутка обзоров на игры

### Платёжные системы
- 💳 **Antilopay** — оплата банковскими картами (Visa, MasterCard, МИР)
- 🪙 **CryptoBot** — оплата криптовалютами (USDT, TON, BTC, ETH и др.)

### Система ценообразования
Динамическое ценообразование — чем больше заказ, тем дешевле:

| Количество | Цена за шт | Скидка |
|------------|-----------|--------|
| 1-99       | 1.00 ₽    | —      |
| 100-199    | 0.85 ₽    | -15%   |
| 200-299    | 0.75 ₽    | -25%   |
| 300-499    | 0.65 ₽    | -35%   |
| 500-999    | 0.60 ₽    | -40%   |
| 1000+      | 0.50 ₽    | -50%   |

## 📋 Требования

- Python 3.10+
- SQLite (или другая БД через SQLAlchemy)

## 🛠 Установка

### 1. Клонирование репозитория

```bash
git clone <repository-url>
cd <repository-name>
```

### 2. Создание виртуального окружения

```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
# или
venv\Scripts\activate  # Windows
```

### 3. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 4. Настройка конфигурации

Скопируйте файл `.env.example` в `.env` и заполните все необходимые параметры:

```bash
cp .env.example .env
```

Отредактируйте `.env`:

```env
# Telegram Bot Configuration
BOT_TOKEN=your_telegram_bot_token
ADMIN_IDS=123456789,987654321

# SteamSmm API Configuration
STEAMSMM_API_URL=http://5.129.240.139:8080
STEAMSMM_API_KEY=user_xxx_your_api_key

# Antilopay Configuration
ANTILOPAY_SECRET_ID=your_secret_id
ANTILOPAY_PRIVATE_KEY=your_private_key_base64
ANTILOPAY_PROJECT_ID=your_project_id
ANTILOPAY_CALLBACK_PUBLIC_KEY=your_callback_public_key_base64

# CryptoBot Configuration
CRYPTOBOT_API_TOKEN=your_cryptobot_token
CRYPTOBOT_TEST_MODE=true

# Webhook Configuration
WEBHOOK_HOST=https://your-domain.com
WEBHOOK_PORT=8443

# Database
DATABASE_URL=sqlite+aiosqlite:///./bot_database.db
```

### 5. Запуск бота

```bash
python run.py
```

## 📁 Структура проекта

```
.
├── bot/
│   ├── __init__.py
│   ├── config.py           # Конфигурация
│   ├── main.py             # Главный файл
│   ├── handlers/           # Обработчики команд
│   │   ├── __init__.py
│   │   ├── start.py        # Старт и базовые команды
│   │   ├── balance.py      # Работа с балансом и оплатой
│   │   ├── boost.py        # Создание заказов на накрутку
│   │   ├── orders.py       # Просмотр заказов
│   │   └── admin.py        # Админ-панель
│   ├── models/             # Модели данных
│   │   ├── __init__.py
│   │   └── database.py     # SQLAlchemy модели
│   ├── services/           # Внешние сервисы
│   │   ├── __init__.py
│   │   ├── steamsmm.py     # Клиент SteamSmm API
│   │   ├── antilopay.py    # Интеграция Antilopay
│   │   ├── cryptobot.py    # Интеграция CryptoBot
│   │   └── webhook.py      # Webhook сервер для платежей
│   └── utils/              # Утилиты
│       ├── __init__.py
│       └── keyboards.py    # Клавиатуры бота
├── requirements.txt        # Зависимости Python
├── .env.example            # Пример конфигурации
├── run.py                  # Точка входа
└── README.md               # Этот файл
```

## 🤖 Команды бота

### Пользовательские команды
- `/start` — Запуск бота
- `/menu` — Главное меню
- `/balance` — Проверка баланса
- `/orders` — Мои заказы
- `/help` — Справка

### Админ-команды
- `/admin` — Панель администратора

## 💳 Настройка платёжных систем

### Antilopay

1. Зарегистрируйтесь на [antilopay.com](https://antilopay.com)
2. Создайте проект в личном кабинете
3. Получите `Secret ID`, приватный ключ и публичный ключ для callback
4. Добавьте URL для callback: `https://your-domain.com/webhook/antilopay`

### CryptoBot

1. Создайте приложение через [@CryptoBot](https://t.me/CryptoBot)
2. Получите API токен
3. Настройте webhook URL: `https://your-domain.com/webhook/cryptobot`

## 🔐 Webhook сервер

Бот автоматически запускает webhook сервер для приёма уведомлений о платежах.

Эндпоинты:
- `POST /webhook/antilopay` — Callback от Antilopay
- `POST /webhook/cryptobot` — Callback от CryptoBot
- `GET /health` — Проверка работоспособности

## 📊 API SteamSmm

Бот использует SteamSmm API для выполнения накрутки.

Документация API: http://5.129.240.139:8080/api/docs

### Поддерживаемые действия:
- `comment` — Комментарии на профиле
- `like` — Лайки на скриншоты/иллюстрации
- `subscribe` — Подписки на группы
- `review` — Обзоры на игры

## 🐳 Docker (опционально)

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "run.py"]
```

```bash
docker build -t steam-smm-bot .
docker run -d --env-file .env -p 8443:8443 steam-smm-bot
```

## 📝 Лицензия

MIT License

## 🤝 Поддержка

При возникновении вопросов обращайтесь к администратору бота.

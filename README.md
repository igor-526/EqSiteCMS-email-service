# Email Service

Сервис отправки email-уведомлений EqSiteCMS. Принимает команды через NATS и Celery.

## Стек

- Python 3.14.6
- FastAPI
- SQLAlchemy Core + asyncpg
- PostgreSQL 17
- Alembic
- NATS Jetstream (команды)
- Celery + Redis (очередь задач)
- Sentry (опционально)

## Архитектура

```text
src/
├── api/             # HTTP-контракты
├── clients/         # NATS клиенты
├── containers/      # DI-контейнер (NATS + Celery)
├── core/            # Бизнес-логика и сервисы
├── depends/         # FastAPI Depends-фабрики
├── models/          # SQLAlchemy Core tables
├── repositories/    # Реализации репозиториев
├── migration/       # Alembic
├── utils/           # Утилиты
├── workers/
│   ├── celery_app.py   # Celery app конфигурация
│   └── tasks/
│       └── email.py    # Задачи отправки email
├── main.py
└── settings.py      # Settings, NatsSettings, CelerySettings
```

## Запуск в Docker

```bash
cp .env.example .env
docker compose -f docker-compose.infra.yml up -d
docker compose -f docker-compose.email.yml up --build
```

Compose запустит API, миграции и celery-worker.

## Celery

### Очереди

| Очередь | Задачи | Описание |
|---------|--------|----------|
| `email` | `email.send` | Отправка email |

### Команды запуска

```bash
# Celery worker (запускается автоматически в docker-compose)
celery -A workers.celery_app worker -Q email -l info

# Мониторинг (опционально)
celery -A workers.celery_app inspect active
```

### Переменные окружения

| Переменная | Значение по умолчанию | Описание |
|------------|----------------------|----------|
| `CELERY_APP_MAIN` | `email-service` | Имя приложения Celery |
| `CELERY_APP_BROKER` | `redis://:<password>@redis:6379/1` | Redis broker (очередь) |
| `CELERY_APP_BACKEND` | `redis://:<password>@redis:6379/2` | Redis backend (результаты) |
| `REDIS_PASSWORD` | — | Пароль Redis |

### Добавление новой задачи

1. Создайте файл в `src/workers/tasks/`
2. Определите задачу с `@shared_task(name="<domain>.<action>")`
3. Задача автоматически зарегистрируется через `autodiscover_tasks`

## Локальная разработка

```bash
cp .env.example .env
uv sync
docker compose -f docker-compose.infra.yml up -d db redis
uv run alembic -c src/alembic.ini upgrade head
uv run uvicorn main:app --app-dir src --reload
```

```bash
make format
make lint
make test
```

## API

| Метод | Путь | Назначение |
|---|---|---|
| GET | `/health` | Healthcheck |

## NATS JetStream

Email Service выступает в роли **Consumer** — принимает команды на отправку email из `NOTIFICATION_COMMANDS`.

| Stream | Subject | Назначение | Роль |
|--------|---------|------------|------|
| NOTIFICATION_COMMANDS | commands.notification.email.send | Приём команды на отправку email | входящий |

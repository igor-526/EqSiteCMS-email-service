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
- Prometheus (production metrics во внутренней сети)

Общая конфигурация Sentry, внутренний Prometheus listener `:9000/metrics`,
sanitization, проверки и rollback описаны в
[`docs/operations/observability.md`](../../docs/operations/observability.md).

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

## SMTP: режим транспорта и миграция

`SMTP_TLS_MODE` принимает только точные значения `tls`, `starttls`, `none`:

| Режим | `use_tls` | `start_tls` | Поведение |
|---|---|---|---|
| `tls` | true | false | TLS немедленно, до SMTP greeting |
| `starttls` | false | true | Обязательный STARTTLS перед авторизацией |
| `none` | false | false | Явный plaintext, только доверенная локальная среда |

Явный режим не зависит от порта: `tls` на 587 и `starttls` на 465 не
переопределяются. Сертификат и имя сервера проверяются (`validate_certs=True`).
Ошибки сертификата, handshake, отсутствия STARTTLS и timeout распространяются
без fallback/downgrade; существующий retry сохраняет выбранный режим.
`none` нельзя использовать как обход TLS failure.

### Совместимость без автоматического downgrade

«Отсутствует» означает удалённую переменную, а не пустую строку.

| `SMTP_TLS_MODE` | Legacy `SMTP_USE_TLS` | Порт | Результат |
|---|---|---|---|
| `tls` | отсутствует / true | любой | `tls` |
| `tls` | false | любой | ошибка конфликта |
| `starttls` | отсутствует / true | любой | `starttls` |
| `starttls` | false | любой | ошибка конфликта |
| `none` | отсутствует / false | любой | `none` |
| `none` | true | любой | ошибка конфликта |
| отсутствует | отсутствует / true | 465 | `tls` |
| отсутствует | отсутствует / true | 587 | `starttls` |
| отсутствует | true | остальные, включая 1127/1126 | `tls` |
| отсутствует | отсутствует | остальные | ошибка: нужен явный режим |
| отсутствует | false | любой | ошибка: требуется явный `none` |
| пустой / невалидный | любой | любой | ошибка валидации |
| любой / отсутствует | пустой / невалидный | любой | ошибка валидации |

Default — порт 587, STARTTLS, обе переменные выбора режима отсутствуют.
Legacy boolean принимает стандартные формы Pydantic (`true/false`, `1/0`,
`on/off`, `yes/no`); режим регистрозависим, без trim (`TLS`, `auto`, пробелы
и пустые строки недопустимы).

**Breaking migration:** прежний sender игнорировал legacy-флаг. Теперь
конфликтующие значения, legacy false без явного `none`, неоднозначный
нестандартный порт и пустые значения останавливают API/worker при создании
settings, до SMTP-сети. Владелец конфигурации должен удалить пустой legacy-флаг
и задать режим явно; не оставлять пустую строку. Конфликтующий legacy удалить
либо согласовать с матрицей. Runtime `.env` автоматически не изменяется.

Рекомендуемые пары (credentials — только через защищённую конфигурацию):

| SMTP host / назначение | `SMTP_PORT` | `SMTP_TLS_MODE` |
|---|---|---|
| Selectel `smtp.mail.selcloud.ru` | 1127 | `tls` |
| Selectel `smtp.mail.selcloud.ru` | 1126 | `starttls` |
| Стандартный implicit TLS | 465 | `tls` |
| Стандартный STARTTLS | 587 | `starttls` |
| Только доверенный локальный SMTP (`localhost`) | 1025 | `none` |

Legacy true + 1126 означает **TLS, не STARTTLS**: для Selectel 1126 обязателен
явный `starttls`. В `.env.example` согласованы 587/`starttls`; legacy удалён.

### Граница доказательств и отдельные разрешения

Локальные mock-тесты проверяют settings и флаги SMTP-клиента, **не доказывают**
внешнюю авторизацию, доставку или отсутствие production timeout. Эти результаты
остаются `unchecked` до отдельной live-проверки. Approval плана не разрешает:

- **G1:** deployment/restart — отдельный permit на revision, среду, ресурс и срок;
- **G2:** внешнюю авторизацию до подтверждения владельцем перевыпуска ранее
  опубликованного API-ключа (значение ключа не передавать; ротация не подтверждена);
- **G3:** live-send — отдельный target/mode/test mailbox/expiry permit и runbook,
  максимум одна отправка на режим, 60 секунд на попытку, stop при первой ошибке;
- **G4:** сбор чувствительных данных — только безопасные outcome/duration,
  deployment fingerprint и receipt-флаг оператора, без credentials, subject/body,
  settings/env dumps и SMTP debug transcripts.

Deployment, ротация и доставка здесь не заявлены выполненными. Без G1..G4
реальная отправка запрещена. При неуспешной выкатке владелец останавливает
отправку и откатывает revision вместе с совместимой конфигурацией по permit.
Старый sender на 1127 не является безопасным рабочим rollback: нельзя
переходить на plaintext. Закрытие без live требует явного waiver пользователя.

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

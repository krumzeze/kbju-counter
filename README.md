# Belok

Сервис для подсчёта калорий и КБЖУ по фото, учёта тренировок, шагов и веса.
Работает в трёх клиентах с общим аккаунтом: Telegram-бот, Telegram Mini App и веб-сайт.

## Возможности

- Фото или текстовое описание блюда: LLM оценивает состав и КБЖУ, порцию можно поправить
- Норма по Миффлину-Сан Жеору с поправкой на шаги, силовые тренировки и цель
- Дневник тренировок и прогресс по упражнениям (расчётный 1ПМ, графики)
- Журнал веса с графиком
- Пробный период 4 дня, дневной лимит распознаваний, учёт стоимости каждого LLM-запроса

## Архитектура

```
Telegram ──▶ bot (aiogram) ─┐
                            ├──▶ PostgreSQL
Mini App / сайт ──▶ nginx ──▶ api (FastAPI) ─┘      Redis (FSM бота)
                     │                 │
                 статика React       Claude Haiku (Anthropic API)
```

Бот и API это два процесса одного Python-пакета `belok` с общими моделями, расчётами и логикой.
Вход в Mini App идёт по `initData`, на сайте через Telegram Login Widget. Обе подписи проверяются
на бэкенде, пользователь определяется по Telegram ID, поэтому данные везде одни.

## Структура

```
services/
  backend/
    src/belok/
      bot/        Telegram bot: handlers, middlewares, texts
      api/        HTTP API: auth, routes, schemas
      domain/     nutrition and workout math, no I/O
      llm/        food analyzer
      services/   DB queries, access rules, shared use cases
      db/         SQLAlchemy models
    migrations/   Alembic
    tests/
  web/            React + Vite: Mini App and website
infra/            Terraform and Ansible, see infra/README.md
deploy/           Helm chart and ArgoCD apps, see deploy/README.md
```

## Настройка

1. Создай бота у @BotFather, возьми токен.
2. Получи API-ключ в platform.claude.com.
3. `cp .env.example .env` и заполни:
   - `BOT_TOKEN`, `LLM_API_KEY`
   - `API_SECRET`: случайная строка от 32 символов (`openssl rand -hex 32`)
   - `BOT_USERNAME`: имя бота без `@`, нужно для входа на сайте
   - `WEBAPP_URL`: публичный HTTPS-адрес сайта, бот повесит на него кнопку меню
4. В @BotFather для входа на сайте: `/setdomain` с доменом сайта.

## Запуск

```bash
docker compose up --build
```

Сайт откроется на http://localhost:8080. Telegram открывает Mini App только по HTTPS, поэтому для
проверки внутри Telegram пробрось порт туннелем (`cloudflared tunnel --url http://localhost:8080`)
и укажи этот адрес в `WEBAPP_URL`.

### Разработка без Docker

```bash
docker compose up -d postgres redis
cd services/backend && uv sync
uv run alembic upgrade head
uv run python -m belok        # bot
uv run python -m belok.api    # API on :8000

cd services/web && npm install
npm run dev                   # http://localhost:5173, /api proxied to :8000
```

## Тесты

```bash
cd services/backend
uv run pytest                                             # unit tests
TEST_DATABASE_URL=postgresql+asyncpg://belok:belok@localhost:5432/belok_test uv run pytest
```

Интеграционные тесты API запускаются, когда задан `TEST_DATABASE_URL`. В CI они идут на
Postgres из service container.

## Roadmap

- [x] Бот: фото и текст в КБЖУ, норма, тренировки, вес, шаги, триал
- [x] API, Mini App и сайт с тем же функционалом
- [ ] Eval моделей на взвешенных блюдах, выбор основной модели
- [x] Инфраструктура как код: Terraform, Ansible, k3s
- [x] GitOps: Helm-чарт, ArgoCD, сборка образов и выкатка из CI
- [ ] Очередь и отдельный vision-worker с автоскейлом (KEDA)
- [ ] Бэкапы Postgres в R2
- [ ] Мониторинг: Prometheus, Grafana, Loki, бизнес-метрики
- [ ] Подписка
- [ ] Синхронизация шагов с Apple Health и Health Connect
- [ ] Адаптивная норма по динамике веса

# Belok

Учёт КБЖУ в Telegram: бот, Mini App и сайт с общим аккаунтом. Блюдо распознаётся по фото или
описанию через Claude Haiku 5.5, дневная норма пересчитывается по шагам и тренировкам.
Дневник тренировок с прогрессом по упражнениям, журнал веса, триал 4 дня и подписка.

## Стек

| | |
|---|---|
| Backend | Python 3.12, aiogram 3, FastAPI, SQLAlchemy 2 (asyncpg), Alembic, PostgreSQL 17, Redis |
| Frontend | React 19, Vite, TanStack Query |
| Infra | Hetzner Cloud, Cloudflare DNS и R2, Terraform, Ansible, k3s |
| Delivery | GitHub Actions, GHCR, Helm, ArgoCD, cert-manager, Sealed Secrets, CloudNativePG |

## Архитектура

```
Telegram ─────────────▶ bot ──┐
                              ├──▶ PostgreSQL
Mini App, сайт ─▶ web ─▶ api ─┘    Redis (FSM бота)
                              └──▶ Anthropic API
```

`bot` и `api` собираются из одного пакета `belok` и делят модели и бизнес-логику. Клиенты
авторизуются по подписи Telegram (`initData` в Mini App, Login Widget на сайте), API выдаёт JWT.
`web` это nginx со статикой и прокси `/api`.

Бот работает через long polling, поэтому всегда одна реплика со стратегией `Recreate`. `api` и
`web` обновляются rolling update без простоя.

## Репозиторий

```
services/backend   bot, API, миграции, тесты
services/web       Mini App и сайт
infra/             Terraform и Ansible: сервер, DNS, k3s
deploy/            Helm-чарт и приложения ArgoCD
```

## Локально

```bash
cp .env.example .env    # BOT_TOKEN, LLM_API_KEY, API_SECRET (openssl rand -hex 32)
docker compose up --build
```

Сайт на http://localhost:8080. Mini App в Telegram открывается только по HTTPS:
`cloudflared tunnel --url http://localhost:8080` и полученный адрес в `WEBAPP_URL`.

Без Docker:

```bash
docker compose up -d postgres redis
cd services/backend && uv sync && uv run alembic upgrade head
uv run python -m belok        # bot
uv run python -m belok.api    # API, :8000
cd services/web && npm install && npm run dev
```

## Тесты

```bash
cd services/backend
uv run pytest
TEST_DATABASE_URL=postgresql+asyncpg://belok:belok@localhost:5432/belok_test uv run pytest
```

Без `TEST_DATABASE_URL` интеграционные тесты API пропускаются.

## Деплой

Push в `main` → тесты → образы в GHCR → CI коммитит новый тег в
`deploy/environments/prod/values.yaml` → ArgoCD выкатывает. Откат через `git revert` этого коммита.

Первичный подъём сервера: [infra/README.md](infra/README.md), кластер и секреты:
[deploy/README.md](deploy/README.md).

## TODO

- Бэкапы Postgres в R2
- Мониторинг и алерты
- Оплата подписки
- Webhook вместо polling для бота
- Eval распознавания на взвешенных блюдах
- Terraform plan/apply из CI

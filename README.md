# Belok

Telegram-бот для подсчёта калорий и КБЖУ по фото, учёта тренировок, шагов и веса.
Дневная норма пересчитывается с учётом активности за день.

## Возможности

- Фото или текстовое описание блюда: LLM оценивает состав и КБЖУ, порцию можно поправить кнопками
- Норма по Миффлину-Сан Жеору с поправкой на шаги, силовые тренировки и цель
- Учёт подходов и прогресс по упражнениям (расчётный 1ПМ)
- Журнал веса
- Пробный период 4 дня, дневной лимит распознаваний, учёт стоимости каждого LLM-запроса

## Стек

Python 3.12, aiogram 3, PostgreSQL, Redis, SQLAlchemy 2 + Alembic, OpenRouter (любая vision-модель).

## Структура

```
services/bot/
  src/belok/
    bot/        handlers, middlewares, keyboards, texts
    domain/     nutrition and workout math, no I/O
    llm/        food analyzer
    services/   DB queries, access rules
    db/         SQLAlchemy models
  migrations/   Alembic
  tests/
```

## Локальный запуск

```bash
cp .env.example .env   # fill in BOT_TOKEN and LLM_API_KEY
docker compose up --build
```

Без Docker для бота:

```bash
docker compose up -d postgres redis
cd services/bot
uv sync
DATABASE_URL=postgresql+asyncpg://belok:belok@localhost:5432/belok uv run alembic upgrade head
uv run python -m belok   # reads .env from the current directory
```

Тесты: `cd services/bot && uv run pytest`

## Roadmap

- [x] MVP бота: фото и текст в КБЖУ, норма, тренировки, вес, шаги, триал
- [ ] Eval моделей на взвешенных блюдах, выбор основной модели
- [ ] Инфраструктура: Terraform, Ansible, k3s, ArgoCD, CI/CD с деплоем
- [ ] Очередь и отдельный vision-worker с автоскейлом (KEDA)
- [ ] Мониторинг: Prometheus, Grafana, Loki, бизнес-метрики
- [ ] Подписка
- [ ] Telegram Mini App с графиками, синхронизация шагов
- [ ] Адаптивная норма по динамике веса

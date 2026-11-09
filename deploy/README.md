# Deploy

ArgoCD синхронизирует кластер с этой папкой в `main` (app of apps, sync waves).
Теги образов лежат отдельно, в ветке `deploy` (`prod.yaml`, `stage.yaml`), их обновляет CI.

| | |
|---|---|
| `argocd/root.yaml` | корневое приложение, ставится Ansible |
| `argocd/apps/` | cert-manager, sealed-secrets, cloudnative-pg, platform, belok-base, belok, belok-stage-base, belok-stage |
| `platform/` | ClusterIssuer Let's Encrypt |
| `belok-base/` | кластер Postgres и SealedSecret прода |
| `belok-stage-base/` | то же для стейджа (namespace `belok-stage`) |
| `charts/belok/` | api, web, bot, redis, job миграций, ingress |
| `environments/{prod,stage}/values.yaml` | значения окружений |

## Первый запуск

1. Пакеты `belok-backend` и `belok-web` в GHCR сделать публичными после первой сборки.
2. Секреты:

```bash
kubectl create secret generic belok-secrets -n belok --dry-run=client -o yaml \
  --from-literal=BOT_TOKEN=... \
  --from-literal=LLM_API_KEY=... \
  --from-literal=API_SECRET=$(openssl rand -hex 32) \
  --from-literal=TRIBUTE_API_KEY=... \
  --from-literal=STT_API_KEY=... \
  | kubeseal --controller-namespace kube-system -o yaml > deploy/belok-base/belok-secrets.yaml
```

3. `BOT_USERNAME` и `ADMIN_ID` (свой Telegram ID) в `environments/prod/values.yaml`, закоммитить
   вместе с секретом. Без `ADMIN_ID` админом становится первый пользователь.
4. В @BotFather `/setdomain` для Login Widget.
5. В Tribute: «Настройки» → «API-ключи» → «URL вебхука» = `https://<host>/api/payments/tribute`.
   Коды товаров из ссылок `web.tribute.tg/p/<код>` и сроки в днях задаёт `TRIBUTE_PLANS`.
6. Голосовые сообщения работают, только если задан `STT_API_KEY`: ключ любого
   OpenAI-совместимого API распознавания речи, адрес и модель в `STT_BASE_URL` и `STT_MODEL`.
7. Фото еды хранятся в R2-бакете `belok-photos` (создаёт Terraform), без ключей не сохраняются.
   В Cloudflare: R2 → Manage API tokens → Object Read & Write только на `belok-photos`, затем:

```bash
kubectl create secret generic belok-secrets -n belok --dry-run=client -o yaml \
  --from-literal=R2_ENDPOINT=https://<account_id>.r2.cloudflarestorage.com \
  --from-literal=R2_ACCESS_KEY_ID=... \
  --from-literal=R2_SECRET_ACCESS_KEY=... \
  | kubeseal --controller-namespace kube-system -o yaml \
    --merge-into deploy/belok-base/belok-secrets.yaml
```

## Стейдж и выкатка

Push в `main`: проверки, образы, сразу деплой на `stage.belok.hamdcreative.com`. Прод получает тот же
SHA только после Approve в GitHub Environment `production` (Settings → Environments → production →
Required reviewers). Если до Approve пришёл новый push, старый ожидающий деплой отменяется.

На стейдже отдельный бот, своя база и Redis, оплата и фото выключены. Секреты стейджа:

```bash
kubectl create secret generic belok-secrets -n belok-stage --dry-run=client -o yaml \
  --from-literal=BOT_TOKEN=<токен стейдж-бота> \
  --from-literal=LLM_API_KEY=... \
  --from-literal=API_SECRET=$(openssl rand -hex 32) \
  | kubeseal --controller-namespace kube-system -o yaml > deploy/belok-stage-base/belok-secrets.yaml
```

`BOT_USERNAME` стейдж-бота прописать в `environments/stage/values.yaml`, в @BotFather сделать
`/setdomain` на `stage.belok.hamdcreative.com`.

## Операции

```bash
kubectl -n argocd get applications
kubectl -n argocd port-forward svc/argocd-server 8443:443
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d
```

Строка подключения к Postgres лежит в секрете `belok-db-app`, его создаёт CloudNativePG.

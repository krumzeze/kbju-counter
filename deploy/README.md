# Deploy

ArgoCD синхронизирует кластер с этой папкой в `main` (app of apps, sync waves).

| | |
|---|---|
| `argocd/root.yaml` | корневое приложение, ставится Ansible |
| `argocd/apps/` | cert-manager, sealed-secrets, cloudnative-pg, platform, belok-base, belok |
| `platform/` | ClusterIssuer Let's Encrypt |
| `belok-base/` | кластер Postgres и SealedSecret приложения |
| `charts/belok/` | api, web, bot, redis, job миграций, ingress |
| `environments/prod/values.yaml` | значения прода, `image.tag` обновляет CI |

## Первый запуск

1. Пакеты `belok-backend` и `belok-web` в GHCR сделать публичными после первой сборки.
2. Секреты:

```bash
kubectl create secret generic belok-secrets -n belok --dry-run=client -o yaml \
  --from-literal=BOT_TOKEN=... \
  --from-literal=LLM_API_KEY=... \
  --from-literal=API_SECRET=$(openssl rand -hex 32) \
  | kubeseal --controller-namespace kube-system -o yaml > deploy/belok-base/belok-secrets.yaml
```

3. `BOT_USERNAME` в `environments/prod/values.yaml`, закоммитить вместе с секретом.
4. В @BotFather `/setdomain` для Login Widget.

## Операции

```bash
kubectl -n argocd get applications
kubectl -n argocd port-forward svc/argocd-server 8443:443
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d
```

Строка подключения к Postgres лежит в секрете `belok-db-app`, его создаёт CloudNativePG.

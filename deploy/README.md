# Deploy

GitOps: состояние кластера описано в этой папке, ArgoCD синхронизирует его с `main`.

```
push в main ──▶ CI: тесты ──▶ образы в GHCR ──▶ коммит с новым тегом в environments/prod
                                                         │
                                       ArgoCD видит изменение ──▶ выкатывает в k3s
```

| Путь | Что это |
|---|---|
| `argocd/root.yaml` | корневое приложение, его ставит Ansible |
| `argocd/apps/` | приложения ArgoCD: cert-manager, sealed-secrets, CloudNativePG, platform, belok-base, belok |
| `platform/` | ClusterIssuer Let's Encrypt |
| `belok-base/` | Postgres (CloudNativePG) и зашифрованные секреты приложения |
| `charts/belok/` | Helm-чарт: api, web, bot, redis, миграции, ingress |
| `environments/prod/values.yaml` | настройки прода, тег образа обновляет CI |

## Первый деплой

1. Подними сервер по `infra/README.md`. Ansible поставит ArgoCD и корневое приложение.
2. После первого прогона CI в GitHub открой Packages → `belok-backend` и `belok-web` →
   Package settings и сделай их публичными. Иначе кластеру нужен `imagePullSecrets`.
3. Создай секреты приложения и зашифруй их ключом кластера:

```bash
kubectl create secret generic belok-secrets -n belok --dry-run=client -o yaml \
  --from-literal=BOT_TOKEN=... \
  --from-literal=LLM_API_KEY=... \
  --from-literal=API_SECRET=$(openssl rand -hex 32) \
  | kubeseal --controller-namespace kube-system -o yaml > deploy/belok-base/belok-secrets.yaml
git add deploy/belok-base/belok-secrets.yaml && git commit -m "Add app secrets" && git push
```

Зашифрованный файл безопасно хранить в git: расшифровать его может только контроллер в кластере.

4. Впиши `BOT_USERNAME` в `environments/prod/values.yaml` и запушь.

## Полезное

```bash
kubectl -n argocd get applications
kubectl -n argocd port-forward svc/argocd-server 8443:443   # UI on https://localhost:8443
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d
kubectl -n belok get pods
```

Откат: `git revert` коммита `Deploy ...` в `main`, ArgoCD вернёт предыдущую версию.

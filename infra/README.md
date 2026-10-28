# Infrastructure

Один сервер Hetzner Cloud с k3s, DNS и бакет для бэкапов в Cloudflare. Terraform создаёт ресурсы
и генерирует inventory для Ansible, Ansible настраивает сервер и ставит k3s.

```
Terraform ──▶ Hetzner: server, firewall, SSH key
          ──▶ Cloudflare: DNS (belok, grafana.belok, argocd.belok), R2 bucket for backups
          ──▶ ansible/inventory/hosts.yml
Ansible   ──▶ admin user, SSH hardening, fail2ban, auto updates, k3s, ArgoCD ──▶ ansible/kubeconfig
```

## Что нужно заранее

- Hetzner Cloud: проект и API-токен с правами Read & Write.
- Cloudflare API-токен с правами `Zone:DNS:Edit` на зону `hamdcreative.com` и `Account:Workers R2 Storage:Edit`.
- Cloudflare R2: бакет `belok-tfstate` (создаётся вручную один раз) и R2 API-токен
  (Access Key ID и Secret) для стейта Terraform.
- SSH-ключ `~/.ssh/id_ed25519`.

## 1. Terraform

```bash
cd infra/terraform
cp terraform.tfvars.example terraform.tfvars   # account id and your IP in admin_cidrs
cp backend.hcl.example backend.hcl             # account id in the endpoint

export HCLOUD_TOKEN=...
export CLOUDFLARE_API_TOKEN=...
export AWS_ACCESS_KEY_ID=...        # R2 token for the state bucket
export AWS_SECRET_ACCESS_KEY=...

terraform init -backend-config=backend.hcl
terraform plan
terraform apply
```

## 2. Ansible

```bash
cd infra/ansible
export ANSIBLE_CONFIG=$PWD/ansible.cfg   # needed on /mnt/* in WSL, the directory is world-writable

ansible-playbook bootstrap.yml   # once, as root: creates the deploy user
ansible-playbook site.yml        # hardening, k3s and ArgoCD, safe to rerun

export KUBECONFIG=$PWD/kubeconfig
kubectl get nodes
```

После `site.yml` вход под root и по паролю закрыт, SSH доступен только пользователю `deploy`
и только с адресов из `admin_cidrs`.

Дальше кластером управляет ArgoCD, см. `deploy/README.md`.

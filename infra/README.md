# Infra

Terraform создаёт сервер Hetzner, firewall, DNS-записи и R2-бакет для бэкапов, затем пишет
inventory для Ansible. Ansible делает hardening и ставит k3s и ArgoCD. Дальше кластером управляет
ArgoCD.

## Требования

- Hetzner Cloud API token (Read & Write)
- Cloudflare API token: `Zone:Read` и `DNS:Edit` на зону, `Workers R2 Storage:Edit`
- R2-бакет `belok-tfstate` и R2 API token к нему для state
- `~/.ssh/id_ed25519`

```bash
export HCLOUD_TOKEN=... CLOUDFLARE_API_TOKEN=...
export AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=...    # R2 token, S3-compatible backend
```

## Terraform

```bash
cd infra/terraform
cp terraform.tfvars.example terraform.tfvars    # account id, admin_cidrs
cp backend.hcl.example backend.hcl              # account id in endpoint
terraform init -backend-config=backend.hcl
terraform apply
```

SSH и Kubernetes API открыты только для `admin_cidrs`.

## Ansible

```bash
cd infra/ansible
export ANSIBLE_CONFIG=$PWD/ansible.cfg    # WSL: /mnt/* is world-writable
ansible-playbook bootstrap.yml            # once, as root
ansible-playbook site.yml
export KUBECONFIG=$PWD/kubeconfig
```

`bootstrap.yml` создаёт пользователя `deploy`, после `site.yml` вход под root и по паролю закрыт.
`site.yml` идемпотентен.

## Удаление

```bash
terraform destroy
```

Непустой бакет `belok-backups` нужно очистить заранее.

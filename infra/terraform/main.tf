locals {
  name     = "belok"
  app_host = "${var.subdomain}.${var.domain}"
  hosts    = ["", "grafana.", "argocd."]
}

resource "hcloud_ssh_key" "admin" {
  name       = "${local.name}-admin"
  public_key = file(pathexpand(var.ssh_public_key_path))
}

resource "hcloud_firewall" "node" {
  name = "${local.name}-node"

  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "22"
    source_ips = var.admin_cidrs
  }

  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "6443"
    source_ips = var.admin_cidrs
  }

  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "80"
    source_ips = ["0.0.0.0/0", "::/0"]
  }

  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "443"
    source_ips = ["0.0.0.0/0", "::/0"]
  }

  rule {
    direction  = "in"
    protocol   = "icmp"
    source_ips = ["0.0.0.0/0", "::/0"]
  }
}

resource "hcloud_server" "node" {
  name         = "${local.name}-1"
  server_type  = var.server_type
  image        = "ubuntu-24.04"
  location     = var.location
  ssh_keys     = [hcloud_ssh_key.admin.id]
  firewall_ids = [hcloud_firewall.node.id]

  public_net {
    ipv4_enabled = true
    ipv6_enabled = true
  }

  labels = {
    app  = local.name
    role = "k3s-server"
  }

  lifecycle {
    ignore_changes = [image, ssh_keys]
  }
}

data "cloudflare_zone" "main" {
  filter = {
    name = var.domain
  }
}

resource "cloudflare_dns_record" "app" {
  for_each = toset(local.hosts)

  zone_id = data.cloudflare_zone.main.id
  name    = "${each.value}${local.app_host}"
  type    = "A"
  content = hcloud_server.node.ipv4_address
  ttl     = 300
  proxied = false
}

resource "cloudflare_r2_bucket" "backups" {
  account_id = var.cloudflare_account_id
  name       = "${local.name}-backups"
}

resource "local_file" "ansible_inventory" {
  filename        = "${path.module}/../ansible/inventory/hosts.yml"
  file_permission = "0644"
  content = yamlencode({
    all = {
      hosts = {
        (hcloud_server.node.name) = {
          ansible_host = hcloud_server.node.ipv4_address
          k3s_tls_sans = [hcloud_server.node.ipv4_address, local.app_host]
        }
      }
    }
  })
}

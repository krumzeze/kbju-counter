output "server_ipv4" {
  value = hcloud_server.node.ipv4_address
}

output "server_ipv6" {
  value = hcloud_server.node.ipv6_address
}

output "app_url" {
  value = "https://${local.app_host}"
}

output "backups_bucket" {
  value = cloudflare_r2_bucket.backups.name
}

variable "domain" {
  type    = string
  default = "hamdcreative.com"
}

variable "subdomain" {
  type    = string
  default = "belok"
}

variable "cloudflare_account_id" {
  type = string
}

variable "server_type" {
  type    = string
  default = "cx33"
}

variable "location" {
  type    = string
  default = "fsn1"
}

variable "ssh_public_key_path" {
  type    = string
  default = "~/.ssh/id_ed25519.pub"
}

variable "admin_cidrs" {
  description = "Addresses allowed to reach SSH and the Kubernetes API."
  type        = list(string)
}

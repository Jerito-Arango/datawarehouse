variable "region" {
  type    = string
  default = "us-east-2"
}
variable "project" {
  type    = string
  default = "dw-user10"
}
variable "owner" {
  type    = string
  default = "de-gr01-user-10"
}

variable "my_ip" {
  type        = string
  description = "Tu IP pública con /32 (curl https://checkip.amazonaws.com)"
}

# Roles existentes (no se crean)
variable "redshift_role_arn" {
  type    = string
  default = ""
}
variable "ec2_role_arn" {
  type    = string
  default = ""
}
variable "ec2_instance_profile" {
  type    = string
  default = ""
}
variable "ssh_public_key_path" {
  type    = string
  default = "~/.ssh/dw-user10.pub"
}

# Interruptores por etapa
variable "enable_redshift" {
  type    = bool
  default = false
}
variable "enable_rds" {
  type    = bool
  default = false
}
variable "enable_docdb" {
  type    = bool
  default = false
}
variable "enable_ec2" {
  type    = bool
  default = false
}

variable "redshift_base_capacity" {
  type    = number
  default = 8
}
variable "docdb_password" {
  type      = string
  sensitive = true
  default   = ""
}
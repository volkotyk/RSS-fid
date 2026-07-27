variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Short prefix applied to every resource name and tag"
  type        = string
  default     = "rssfid"
}

variable "environment" {
  description = "Deployment environment label"
  type        = string
  default     = "prod"
}

variable "podcast_title" {
  description = "Human-readable title in the RSS <channel> element"
  type        = string

  validation {
    condition     = length(trimspace(var.podcast_title)) > 0
    error_message = "podcast_title must not be empty."
  }
}

variable "podcast_description" {
  description = "Short description in the RSS <channel> element"
  type        = string

  validation {
    condition     = length(trimspace(var.podcast_description)) > 0
    error_message = "podcast_description must not be empty."
  }
}

variable "podcast_author" {
  description = "Author name in <itunes:author>"
  type        = string

  validation {
    condition     = length(trimspace(var.podcast_author)) > 0
    error_message = "podcast_author must not be empty."
  }
}

variable "podcast_language" {
  description = "BCP 47 language code for <language>, e.g. 'en' or 'uk'"
  type        = string
  default     = "en"
}

variable "podcast_category" {
  description = "Apple Podcasts top-level category for <itunes:category>"
  type        = string
  default     = "Education"
}

variable "podcast_owner_name" {
  description = "Owner display name inside <itunes:owner>"
  type        = string

  validation {
    condition     = length(trimspace(var.podcast_owner_name)) > 0
    error_message = "podcast_owner_name must not be empty."
  }
}

variable "podcast_owner_email" {
  description = "Owner contact email inside <itunes:owner>"
  type        = string

  validation {
    condition     = can(regex("^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$", var.podcast_owner_email))
    error_message = "podcast_owner_email must be a valid email address."
  }
}

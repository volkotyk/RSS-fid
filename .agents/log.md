# Agent Change Log

## [2026-07-27] Public repository preparation

- Replaced the template README with project architecture, setup, deployment,
  configuration, media-upload, CI/CD, security, cleanup, and limitation details.
- Added public-repository ignore rules for secrets, Terraform state and plans,
  generated packages, caches, IDE state, captured endpoints, and local media.
- Added deterministic line-ending rules for cross-platform contributions.
- Made personal podcast metadata explicit Terraform inputs and documented the
  corresponding `TF_VAR_*` environment variables.
- Reworked GitHub Actions to validate source changes without AWS credentials and
  to deploy only through an explicit manual workflow using GitHub Variables and
  Secrets.
- Updated project security and release state for the public repository model.
- Corrected stale agent guidance that claimed an unimplemented ACM/Route53
  custom-domain layer and documented the actual required Terraform inputs.

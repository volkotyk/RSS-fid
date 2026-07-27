# Project State

## Current blocking issues

- None recorded.

## Security mandates

- Never commit AWS credentials, real `*.tfvars`, Terraform state or plans,
  generated packages, local media, personal email addresses, or deployed API
  endpoints.
- Keep S3 Block Public Access enabled and the Lambda execution role limited to
  listing and reading the generated podcast bucket.
- Treat the API Gateway feed and redirect routes as public until an explicit
  authorization layer is implemented.
- Use only mocked AWS services in automated tests.

## Release risks

- The feed has no subscriber authentication or rate limiting.
- Terraform uses local state unless the operator configures a protected remote
  backend.
- The owner email is published in RSS XML by design.
- Manual GitHub deployment requires repository/environment variables and AWS
  secrets to be configured first.

## Recently completed

- Prepared the repository for public release by excluding local state and media,
  parameterizing deployment metadata, documenting setup, and making AWS deploys
  manual.

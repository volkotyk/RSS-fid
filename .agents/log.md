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

## [2026-07-27] YouTube Music RSS listening guide

- Added an end-to-end README walkthrough for obtaining and validating the
  deployed feed URL, subscribing in the YouTube Music mobile app, listening,
  downloading episodes, understanding RSS limitations, and troubleshooting
  common feed, media, artwork, and redirect problems.

## [2026-07-27] Apple Podcasts and Spotify listening guides

- Documented direct RSS following and optional public catalog submission for
  Apple Podcasts on iPhone, iPad, and Mac, clarifying that Apple Music is not the
  podcast RSS client.
- Documented Spotify for Creators ownership verification, catalog listening,
  feed updates, troubleshooting, and the public-distribution implications of
  using Spotify instead of a personal RSS subscription.

# RSS-feed

`RSS-feed` is a serverless RSS 2.0 feed generator for an S3-backed podcast. An
AWS Lambda function lists audio objects in a private S3 bucket, renders an RSS
feed with Apple Podcasts metadata, and serves it through an API Gateway HTTP
API. Audio and artwork stay private in S3 and are delivered through short-lived
pre-signed URL redirects.

The project is designed for a small personal podcast and uses Free Tier-conscious
defaults: Python 3.12, 128 MB Lambda memory, a 29-second timeout, S3-managed
encryption, and seven-day CloudWatch log retention.

> [!IMPORTANT]
> The S3 bucket is private, but the API Gateway routes are public. Anyone who
> knows the feed URL can read the RSS feed and follow its media links. This is
> not an authenticated or access-controlled podcast feed.

## Features

- Generates RSS 2.0 XML with the Apple Podcasts `itunes` namespace.
- Discovers `.mp3`, `.wav`, `.m4a`, `.aac`, `.ogg`, and `.flac` objects through
  paginated S3 listings.
- Percent-encodes spaces and non-ASCII S3 keys in enclosure URLs.
- Returns exact S3 object sizes and extension-based MIME types in enclosures.
- Serves cover art, episode artwork, and audio through one-hour S3 pre-signed
  URLs while keeping the bucket blocked from public access.
- Provisions S3, Lambda, API Gateway, CloudWatch, and least-privilege IAM with
  Terraform.
- Tests all application branches with `pytest` and `moto`; CI enforces 100%
  statement and branch coverage without contacting AWS.

## Architecture

```mermaid
flowchart LR
    P["Podcast client"] -->|"GET /feed"| A["API Gateway HTTP API"]
    A --> L["Python 3.12 Lambda"]
    L -->|"ListObjectsV2"| S["Private S3 bucket"]
    L -->|"RSS 2.0 XML"| P
    P -->|"GET /audio/... or /images/..."| A
    L -->|"307 pre-signed URL"| P
    P -->|"Temporary authenticated GET"| S
    L --> C["CloudWatch Logs"]
```

Terraform derives the globally unique bucket name as
`<project_name>-audio-<aws_account_id>`; no account ID, bucket name, endpoint,
email address, or podcast metadata is committed to the repository.

## HTTP routes

| Route | Response |
| --- | --- |
| `GET /feed` | RSS 2.0 XML; cached by clients for five minutes. |
| `GET /cover` | `307` redirect to the S3 object `images/cover.png`. |
| `GET /audio/{key}` | `307` redirect to the requested audio object. |
| `GET /images/{key}` | `307` redirect to an object below `images/`. |

Audio files whose basename starts with `<number>.` automatically reference
`images/<number>.png` as episode artwork. For example,
`3. Introduction.m4a` maps to `images/3.png`.

## Repository layout

```text
src/handler.py                 Lambda entry point and RSS renderer
tests/                         moto-backed pytest suite
infra/main.tf                  S3, Lambda, API Gateway, and CloudWatch
infra/iam.tf                   Lambda execution role and policies
infra/variables.tf             Deployment inputs
infra/outputs.tf               Feed, cover, bucket, and log outputs
infra/terraform.tfvars.example Safe configuration example
.github/workflows/ci.yml        Tests, Terraform checks, and manual deploy
docs/STATE.md                  Current security and release notes
```

Local Terraform state, real variable files, build artifacts, IDE settings,
audio, and artwork are intentionally ignored by Git. Podcast media belongs in
the deployed S3 bucket and can be many times larger than GitHub's file limits.

## Prerequisites

- Python 3.12 or newer for local development.
- Terraform 1.5 or newer.
- An AWS account and AWS credentials available through the standard AWS SDK
  credential chain, such as an AWS profile or environment variables.
- Permission to create S3, Lambda, API Gateway v2, CloudWatch Logs, and IAM
  resources in the selected account.

AWS may charge for deployed resources when account allowances are exceeded.
Review the plan before applying it.

## Local development

Create and activate a virtual environment, then install the test dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

Run the full test and coverage gate:

```powershell
python -m pytest tests --cov=src --cov-branch --cov-report=term-missing --cov-fail-under=100
```

All AWS calls in the test suite are intercepted by `moto`. The credentials in
`tests/conftest.py` are deliberately fake test values.

## Configuration with environment variables

Terraform automatically reads environment variables named `TF_VAR_<variable>`.
Using them keeps personal values out of source files and command history. Set
the required podcast metadata in the current shell before planning or applying:

```powershell
$env:TF_VAR_podcast_title = "My Podcast"
$env:TF_VAR_podcast_description = "A short description of the podcast"
$env:TF_VAR_podcast_author = "Publisher name"
$env:TF_VAR_podcast_owner_name = "Owner name"
$env:TF_VAR_podcast_owner_email = "owner@example.com"

# Optional overrides
$env:TF_VAR_aws_region = "us-east-1"
$env:TF_VAR_project_name = "rss-feed"
$env:TF_VAR_environment = "prod"
$env:TF_VAR_podcast_language = "en"
$env:TF_VAR_podcast_category = "Education"
```

| Terraform variable | Environment variable | Required | Default | Purpose |
| --- | --- | :---: | --- | --- |
| `podcast_title` | `TF_VAR_podcast_title` | Yes | — | RSS channel title. |
| `podcast_description` | `TF_VAR_podcast_description` | Yes | — | RSS and Apple Podcasts summary. |
| `podcast_author` | `TF_VAR_podcast_author` | Yes | — | Apple Podcasts author. |
| `podcast_owner_name` | `TF_VAR_podcast_owner_name` | Yes | — | Owner display name. |
| `podcast_owner_email` | `TF_VAR_podcast_owner_email` | Yes | — | Owner email published inside the RSS feed. |
| `aws_region` | `TF_VAR_aws_region` | No | `us-east-1` | AWS deployment region. |
| `project_name` | `TF_VAR_project_name` | No | `rss-feed` | Resource-name and tag prefix. |
| `environment` | `TF_VAR_environment` | No | `prod` | Environment tag. |
| `allow_destroy_media_deletion` | `TF_VAR_allow_destroy_media_deletion` | No | `false` | Allows a reviewed destroy operation to empty and delete the podcast bucket. |
| `podcast_language` | `TF_VAR_podcast_language` | No | `en` | BCP 47 feed language. |
| `podcast_category` | `TF_VAR_podcast_category` | No | `Education` | Apple Podcasts top-level category. |

As an alternative, copy `infra/terraform.tfvars.example` to
`infra/terraform.tfvars` and edit it locally. Real `*.tfvars` files are ignored
and must never be committed.

The Lambda runtime receives its own environment variables from Terraform:
`BUCKET_NAME`, `PODCAST_TITLE`, `PODCAST_DESCRIPTION`, `PODCAST_AUTHOR`,
`PODCAST_LINK`, `PODCAST_IMAGE_URL`, `PODCAST_LANGUAGE`, `PODCAST_CATEGORY`,
`PODCAST_OWNER_NAME`, and `PODCAST_OWNER_EMAIL`. The API URL, cover URL, and
bucket name are derived from provisioned resources rather than supplied by a
person.

## Deploy to AWS

Authenticate with AWS through your preferred standard mechanism. For example,
select an existing local profile without putting credentials in the repository:

```powershell
$env:AWS_PROFILE = "my-aws-profile"
```

Then initialize, review, and apply the Terraform configuration:

```powershell
terraform -chdir=infra init
terraform -chdir=infra fmt -check -recursive
terraform -chdir=infra validate
terraform -chdir=infra plan -out=tfplan
terraform -chdir=infra apply tfplan
```

Read the generated resource names and URLs:

```powershell
terraform -chdir=infra output
```

## Upload podcast media

Use the Terraform output instead of hard-coding the account-specific bucket
name:

```powershell
$bucket = terraform -chdir=infra output -raw s3_bucket_name
aws s3 cp ".\audio\episode-001.mp3" "s3://$bucket/episode-001.mp3"
aws s3 cp ".\images\cover.png" "s3://$bucket/images/cover.png"
aws s3 cp ".\images\1.png" "s3://$bucket/images/1.png"
```

To upload a whole local media directory, use `aws s3 sync` only after checking
that the source directory contains exactly the files intended for this bucket.
The Lambda reads object size and modification time directly from S3, so a new
feed request reflects uploads without a separate database or index.

## Listen in YouTube Music with the RSS feed

Google's current podcast player is YouTube Music. It can add a podcast directly
from its RSS URL in the Android or iOS app. Google requires an adult (18+)
account for RSS subscriptions. See the official
[YouTube Music RSS instructions](https://support.google.com/youtubemusic/answer/13946190).

### 1. Deploy the feed and upload media

Complete the Terraform deployment and upload at least one supported audio file
to the generated S3 bucket. Upload `images/cover.png` as well if the podcast
should display cover artwork.

### 2. Copy the public feed URL

Read the URL from the Terraform state instead of copying an account-specific
API Gateway hostname into documentation or source code:

```powershell
$feedUrl = terraform -chdir=infra output -raw rss_feed_url
$feedUrl
```

The value should be an HTTPS URL ending in `/feed`, for example
`https://<api-id>.execute-api.<region>.amazonaws.com/feed`.

### 3. Verify the feed before adding it

The feed must be reachable from the public internet because YouTube Music fetches
it from Google's servers. Check the response from a machine with internet access:

```powershell
$response = Invoke-WebRequest -Uri $feedUrl -UseBasicParsing
$response.StatusCode
$response.Headers["Content-Type"]
```

Expect status `200` and a content type beginning with `application/rss+xml`.
Opening `$feedUrl` in a browser should also display or download XML containing
an `<rss>` element and at least one `<item>` after media has been uploaded.

### 4. Add the RSS URL in the YouTube Music mobile app

1. Open **YouTube Music** on Android or iOS and sign in with an adult Google
   Account.
2. Tap **Library**.
3. Select **Podcasts** at the top of the screen.
4. Tap **Add podcast** in the bottom-right corner.
5. Select **Add a podcast by RSS feed**.
6. Read and accept Google's RSS-feed disclaimer.
7. Paste the `$feedUrl` value from step 2.
8. Tap **Add**.
9. Wait for the show to appear under **Library → Podcasts**. Google says most
   feeds appear within minutes, although some take longer. RSS-based shows have
   an RSS badge next to their title.

### 5. Listen and optionally download episodes

1. Open **Library → Podcasts** and select the newly added show.
2. Select an episode and tap **Play**.
3. To listen later without a connection, open the episode menu and select
   **Download** when that option is available.

Google documents that podcast downloads are generally available without a
Premium membership, although some shows or episodes may not support an
audio-only download. See the official
[offline listening guide](https://support.google.com/youtubemusic/answer/6313535).
Most podcasts can also continue playing in the background without Premium.

You do not need to re-add the URL after uploading another episode. YouTube Music
periodically refreshes the same feed. `RSS-feed` asks clients to cache the RSS XML
for five minutes, and YouTube Music may take additional time to fetch an update.

### Troubleshooting YouTube Music

| Problem | What to check |
| --- | --- |
| **Add a podcast by RSS feed** is missing | Confirm that this is the YouTube Music mobile app and that the signed-in Google Account is an adult account. |
| YouTube Music rejects the URL | Use the `rss_feed_url` Terraform output, including HTTPS and the final `/feed`; do not paste the `/cover` URL or an S3 URL. |
| The feed returns an error | Run the verification command above, confirm the Lambda and S3 bucket still exist, then inspect the `cloudwatch_log_group` Terraform output. |
| The show appears without episodes | Upload at least one file with a supported audio extension and request `/feed` again to confirm that the XML contains an `<item>`. |
| Artwork is missing | Upload the cover as `images/cover.png`. For numbered episode files such as `1. Introduction.mp3`, upload episode artwork as `images/1.png`. |
| An episode is listed but will not play | Confirm that its S3 object still exists and that its `/audio/...` enclosure URL returns a `307` redirect rather than `404` or `502`. |

RSS-added shows do not support every native YouTube Music feature. Google lists
audio/video switching, likes and dislikes, sharing, channel pages, reporting,
and captions as unavailable. Google also warns that the RSS host can receive the
listener's IP address. In this project, both the feed URL and its API routes are
public, so do not treat possession of the URL as strong access control.

## Listen in Apple Podcasts

Podcast RSS feeds are handled by the **Apple Podcasts** app, not Apple Music.
Apple Podcasts can follow the `RSS-feed` URL directly for personal listening; the
show does not need to be submitted to Apple's public catalog first. See Apple's
official guide for
[adding a show by URL on iPhone](https://support.apple.com/en-gb/guide/iphone/iph19bb8e705/ios).

### iPhone or iPad

1. Obtain and verify `$feedUrl` using steps 2 and 3 in the YouTube Music section
   above.
2. Open the **Podcasts** app.
3. Tap **Library**.
4. Tap the **More** button (`…`).
5. Select **Follow a Show by URL**.
6. Paste `$feedUrl`, including HTTPS and the final `/feed`.
7. Tap **Follow**.
8. Open the show from **Library**, select an episode, and tap **Play**.
9. To listen offline, touch and hold an episode and select **Download**. Apple
   documents the current download flow in its
   [Apple Podcasts download guide](https://support.apple.com/en-us/102243).

### Mac

1. Open the **Podcasts** app.
2. From the menu bar, choose **File → Follow a Show by URL**.
3. Paste `$feedUrl` and click **Follow**.
4. Open the show from the sidebar and play or download an episode.

These steps follow the feed only in the listener's Apple Podcasts library. They
do not make the show searchable in Apple's public catalog. If public discovery
is desired, use [Apple Podcasts Connect](https://podcastsconnect.apple.com/):

1. Click **Add (`+`) → New Show**.
2. Choose **Add a show with an RSS feed** and enter `$feedUrl`.
3. Review the imported show information and confirm the content rights.
4. Add contact information, then configure countries or regions, distribution,
   transcripts, and release timing under **Availability**.
5. Save and publish the show. Apple validates the feed and reviews the show
   before making it available in Apple Podcasts.

The complete public-catalog workflow and its review requirements are documented
in Apple's official
[Submit a new show guide](https://podcasters.apple.com/support/897-submit-a-show).

## Publish and listen on Spotify

Spotify's normal listener app does not provide a general-purpose **Add podcast
by RSS URL** flow like YouTube Music or Apple Podcasts. To listen to a
self-hosted `RSS-feed` show in Spotify, add or claim the externally hosted show
through Spotify for Creators. This creates a Spotify catalog listing; use Apple
Podcasts or YouTube Music instead if the feed should remain only a personal
library entry.

### 1. Prepare the feed for Spotify verification

1. Deploy the feed and upload at least one episode and the cover artwork.
2. Verify that `$feedUrl` returns status `200` and valid RSS XML.
3. Confirm that `TF_VAR_podcast_owner_email` is an address you can access.
   `RSS-feed` publishes this value in `<itunes:email>`, and Spotify sends its
   ownership code to the email address found in the RSS feed.
4. Confirm that you own or have permission to distribute all included content.

### 2. Add or claim the externally hosted show

1. Go to [Spotify for Creators](https://creators.spotify.com/) and sign in with
   a Spotify account.
2. For a new creator account, select **Find an existing show**, then
   **Somewhere else**. If the account already manages another show, open the
   account menu, select **Add a new show**, then choose **Find an existing show
   → Somewhere else**.
3. Enter `$feedUrl` when prompted for the podcast RSS feed or Spotify show URL.
4. Request the ownership verification email.
5. Copy the eight-digit code sent to `PODCAST_OWNER_EMAIL` and paste it into the
   Spotify for Creators form.
6. Complete the remaining show details and submission prompts.

Spotify documents these current steps in
[Claiming your podcast on Spotify for Creators](https://support.spotify.com/us/creators/article/claiming-your-podcast-on-spotify-for-creators/).
A show can be claimed only once; an existing administrator must grant access if
Spotify reports that somebody has already claimed it.

### 3. Find and listen to the show

1. Wait for Spotify to finish processing the feed and make the show available.
2. Open the Spotify app and search for the podcast title configured in
   `TF_VAR_podcast_title`.
3. Open the matching show and select **Follow**.
4. Select an episode and tap **Play**. Use Spotify's episode download option if
   it is available for the account and device.

Spotify continues reading the registered RSS URL, so new S3 episodes should
appear after Spotify refreshes the feed; the URL does not need to be submitted
again. If the feed URL changes, update it in **Spotify for Creators → Settings**
instead of creating a duplicate show.

### Spotify troubleshooting and publication warnings

| Problem | What to check |
| --- | --- |
| No verification email arrives | Fetch `$feedUrl`, confirm `<itunes:email>` contains the expected reachable address, and check its spam folder. |
| Spotify rejects or cannot find the feed | Confirm the URL is public HTTPS, ends in `/feed`, returns `200`, contains valid RSS XML, and has at least one episode. |
| The show is already claimed | Ask the current Spotify for Creators administrator to add the required account; a show can be claimed only once. |
| New episodes do not appear | Confirm the new S3 object appears as an `<item>` in `/feed`, then allow time for Spotify to refresh its cached copy. |
| Playback fails | Test the episode's `/audio/...` enclosure URL and confirm it returns a `307` redirect to an unexpired S3 pre-signed URL. |

Submitting to Spotify makes the show discoverable to other Spotify users and
shares the feed metadata with Spotify. It is not a private-subscription feature.
Also, Spotify for Creators is intended for podcasts, not for distributing music
tracks, DJ mixes, or similar music releases.

## GitHub Actions configuration

The workflow runs tests and offline Terraform validation on every push and pull
request. Deployment is intentionally manual through **Actions → RSS Feed
Generator CI/CD → Run workflow**, so publishing or merging source code cannot
silently change an AWS account.

Before using the deploy job, create these GitHub repository or `production`
environment values:

| GitHub Variables | Required | Maps to |
| --- | :---: | --- |
| `AWS_REGION` | No | AWS region; falls back to `us-east-1`. |
| `PROJECT_NAME` | No | `TF_VAR_project_name`; falls back to `rss-feed`. |
| `DEPLOYMENT_ENVIRONMENT` | No | `TF_VAR_environment`; falls back to `prod`. |
| `PODCAST_TITLE` | Yes | `TF_VAR_podcast_title`. |
| `PODCAST_DESCRIPTION` | Yes | `TF_VAR_podcast_description`. |
| `PODCAST_AUTHOR` | Yes | `TF_VAR_podcast_author`. |
| `PODCAST_OWNER_NAME` | Yes | `TF_VAR_podcast_owner_name`. |
| `PODCAST_OWNER_EMAIL` | Yes | `TF_VAR_podcast_owner_email`. |
| `PODCAST_LANGUAGE` | No | Feed language; falls back to `en`. |
| `PODCAST_CATEGORY` | No | Podcast category; falls back to `Education`. |

Store `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` as GitHub **Secrets**, not
Variables. Scope the corresponding AWS principal to the resources and actions
needed by this Terraform configuration. For stronger controls, protect the
`production` GitHub Environment with required reviewers.

## Security and privacy notes

- Terraform state can contain account IDs, resource identifiers, endpoint URLs,
  and podcast metadata. It is ignored and must be stored securely. For team use,
  configure a protected remote backend before sharing state.
- The owner email is deliberately included in the generated RSS XML. Use a
  role-based or alias address if a personal email should not be public.
- S3 public access is blocked and objects use S3-managed AES-256 encryption at
  rest. Media downloads use pre-signed URLs that expire after one hour.
- The Lambda role can list only the generated podcast bucket and read objects
  below that bucket. It has no write or delete permission.
- API Gateway currently has no authentication, rate limiting, or subscriber
  token. Add an authorization layer before treating the feed URL as confidential.
- Do not commit AWS keys, `terraform.tfvars`, Terraform state, plans, generated
  Lambda archives, local media, IDE settings, or captured API endpoints.

## Remove deployed resources

Terraform destroys only resources recorded in the active Terraform state. Use
the same state and AWS account/profile that created the deployment. Back up any
podcast media that must be retained. First, create and inspect a saved plan that
enables deletion of objects in the managed bucket, then apply that plan:

```powershell
terraform -chdir=infra plan -var='allow_destroy_media_deletion=true' -out=enable-destroy.tfplan
terraform -chdir=infra show enable-destroy.tfplan
terraform -chdir=infra apply enable-destroy.tfplan
```

After that setting is recorded in Terraform state, create and inspect the full
destroy plan before applying it:

```powershell
terraform -chdir=infra plan -destroy -var='allow_destroy_media_deletion=true' -out=destroy.tfplan
terraform -chdir=infra show destroy.tfplan
terraform -chdir=infra apply destroy.tfplan
```

Setting `allow_destroy_media_deletion=true` lets the AWS provider permanently
remove every object in the managed S3 bucket so that the bucket can also be
deleted. It defaults to `false` to protect media during routine work. Applying
the reviewed saved plan removes the S3 bucket and its contents, Lambda, API
Gateway, CloudWatch log group, IAM role and policy, and the remaining AWS
resources tracked by this configuration. The operation is irreversible; do not
apply the plan if it contains resources outside this project.

## Current limitations

- The feed and redirect routes are public and have no subscriber authentication.
- Episode duration is emitted as `0`; the Lambda does not inspect audio metadata.
- Episode titles come from S3 keys and are not backed by a separate metadata
  manifest.
- The deployment uses the default API Gateway hostname; custom domains are not
  provisioned.
- Terraform state is local unless you add a remote backend.

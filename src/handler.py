import json
import logging
import os
import re
from datetime import timezone
from email.utils import formatdate
from urllib.parse import quote as _url_quote, unquote as _url_unquote
from xml.sax.saxutils import escape as _xml_escape

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

BUCKET_NAME         = os.environ.get("BUCKET_NAME", "")
PODCAST_TITLE       = os.environ.get("PODCAST_TITLE", "My Podcast")
PODCAST_DESCRIPTION = os.environ.get("PODCAST_DESCRIPTION", "A private podcast feed")
PODCAST_AUTHOR      = os.environ.get("PODCAST_AUTHOR", "Podcast Author")
PODCAST_LINK        = os.environ.get("PODCAST_LINK", "https://example.com")
PODCAST_LANGUAGE    = os.environ.get("PODCAST_LANGUAGE", "en")
# 1400x1400 square JPEG required by Apple Podcasts; override via env var.
PODCAST_IMAGE_URL   = os.environ.get("PODCAST_IMAGE_URL", "https://example.com/podcast-cover.jpg")
PODCAST_CATEGORY    = os.environ.get("PODCAST_CATEGORY", "Education")
PODCAST_OWNER_NAME  = os.environ.get("PODCAST_OWNER_NAME", "Podcast Owner")
PODCAST_OWNER_EMAIL = os.environ.get("PODCAST_OWNER_EMAIL", "owner@example.com")

ITUNES_NS  = "http://www.itunes.com/dtds/podcast-1.0.dtd"
CONTENT_NS = "http://purl.org/rss/1.0/modules/content/"

_AUDIO_EXTENSIONS: frozenset[str] = frozenset(
    {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"}
)
_CONTENT_TYPES: dict[str, str] = {
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".m4a": "audio/mp4",
    ".aac": "audio/aac",
    ".ogg": "audio/ogg",
    ".flac": "audio/flac",
}

s3_client = boto3.client("s3")


def _is_audio_file(key: str) -> bool:
    _, ext = os.path.splitext(key.lower())
    return ext in _AUDIO_EXTENSIONS


def _get_content_type(key: str) -> str:
    _, ext = os.path.splitext(key.lower())
    return _CONTENT_TYPES.get(ext, "audio/mpeg")


def _format_pubdate(dt) -> str:
    """Return an RFC 2822 date string suitable for RSS <pubDate>."""
    ts = dt.replace(tzinfo=timezone.utc).timestamp()
    return formatdate(ts, usegmt=True)


def _item_title(key: str) -> str:
    """Return a human-readable title by stripping the file extension from the S3 key."""
    return os.path.splitext(key)[0]


def _item_image_key(key: str) -> str | None:
    """Return the S3 key for the episode artwork, or None if no match.

    Convention: audio files starting with "{n}." map to "images/{n}.jpg".
    Example: "3. Справжня_ціна.m4a" -> "images/3.jpg"
    """
    match = re.match(r"^(\d+)\.", os.path.basename(key))
    if match:
        return f"images/{match.group(1)}.png"
    return None


def _build_rss_feed(items: list[dict]) -> str:
    """Return a valid RSS 2.0 + Apple Podcasts XML string.

    Namespace declarations are placed on the root <rss> element so that
    podcast validators (Podbase, Castfeed, Apple) accept the feed without
    warnings.  xml.sax.saxutils.escape() is used for all user-supplied text
    to prevent XML injection.
    """
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        # Both namespace declarations are required on the root element.
        f'<rss version="2.0"'
        f' xmlns:itunes="{ITUNES_NS}"'
        f' xmlns:content="{CONTENT_NS}">',
        "  <channel>",
        f"    <title>{_xml_escape(PODCAST_TITLE)}</title>",
        f"    <link>{_xml_escape(PODCAST_LINK)}</link>",
        f"    <description>{_xml_escape(PODCAST_DESCRIPTION)}</description>",
        f"    <language>{_xml_escape(PODCAST_LANGUAGE)}</language>",
        f"    <itunes:author>{_xml_escape(PODCAST_AUTHOR)}</itunes:author>",
        # itunes:summary mirrors the channel description for broad client compat.
        f"    <itunes:summary>{_xml_escape(PODCAST_DESCRIPTION)}</itunes:summary>",
        # "false" is the current Apple-preferred value (older feeds used "no").
        "    <itunes:explicit>false</itunes:explicit>",
        f'    <itunes:image href="{_xml_escape(PODCAST_IMAGE_URL)}"/>',
        f'    <itunes:category text="{_xml_escape(PODCAST_CATEGORY)}"/>',
        "    <itunes:owner>",
        f"      <itunes:name>{_xml_escape(PODCAST_OWNER_NAME)}</itunes:name>",
        f"      <itunes:email>{_xml_escape(PODCAST_OWNER_EMAIL)}</itunes:email>",
        "    </itunes:owner>",
    ]

    for meta in items:
        title = _item_title(meta["key"])
        lines += [
            "    <item>",
            f"      <title>{_xml_escape(title)}</title>",
            f"      <description>{_xml_escape(title)}</description>",
            f"      <pubDate>{meta['pub_date']}</pubDate>",
            # length must be the exact byte size from S3; type is the MIME type.
            f'      <enclosure'
            f' url="{_xml_escape(meta["url"])}"'
            f' length="{meta["size"]}"'
            f' type="{meta["content_type"]}"/>',
            f'      <guid isPermaLink="false">{_xml_escape(meta["key"])}</guid>',
        ]
        image_key = _item_image_key(meta["key"])
        if image_key:
            image_url = f"{PODCAST_LINK}/{_url_quote(image_key, safe='/')}"
            lines.append(f'      <itunes:image href="{_xml_escape(image_url)}"/>')
        lines += [
            f"      <itunes:duration>{meta.get('duration', '0')}</itunes:duration>",
            "    </item>",
        ]

    lines += [
        "  </channel>",
        "</rss>",
    ]

    return "\n".join(lines)


COVER_KEY = "images/cover.png"  # cover moved to images/ alongside episode artwork
# Pre-signed URL TTL in seconds. Lambda execution-role credentials rotate
# roughly on the same cadence, so 1 hour covers any reasonable download time.
PRESIGN_TTL = 3600


def _serve_cover() -> dict:
    """Return a 307 redirect to a short-lived S3 pre-signed URL for cover.png.

    generate_presigned_url is purely client-side and never raises for a missing
    key, so a head_object preflight is used to produce meaningful 404/502
    responses before we hand the redirect to the client.
    """
    try:
        # Will raise ClientError("404") for missing key or
        # ClientError("NoSuchBucket") for missing bucket.
        s3_client.head_object(Bucket=BUCKET_NAME, Key=COVER_KEY)
        url = s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": BUCKET_NAME, "Key": COVER_KEY},
            ExpiresIn=PRESIGN_TTL,
        )
        return {
            "statusCode": 307,
            "headers": {
                "Location": url,
                # Prevent clients from caching the redirect so they always
                # receive a fresh pre-signed URL on the next fetch.
                "Cache-Control": "no-store",
            },
            "body": "",
        }
    except ClientError as exc:
        error_code: str = exc.response["Error"]["Code"]
        logger.error("S3 ClientError fetching cover [%s]: %s", error_code, exc)
        # head_object returns "404" for missing key, "NoSuchBucket" for bad bucket
        status = 404 if error_code in ("404", "NoSuchKey", "NoSuchBucket") else 502
        return {
            "statusCode": status,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Cover image not found", "code": error_code}),
        }


def _serve_audio(key: str) -> dict:
    """Return a 307 redirect to a short-lived S3 pre-signed URL for an audio file."""
    try:
        s3_client.head_object(Bucket=BUCKET_NAME, Key=key)
        url = s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": BUCKET_NAME, "Key": key},
            ExpiresIn=PRESIGN_TTL,
        )
        return {
            "statusCode": 307,
            "headers": {
                "Location": url,
                "Cache-Control": "no-store",
            },
            "body": "",
        }
    except ClientError as exc:
        error_code: str = exc.response["Error"]["Code"]
        logger.error("S3 ClientError fetching audio [%s]: %s", error_code, exc)
        status = 404 if error_code in ("404", "NoSuchKey", "NoSuchBucket") else 502
        return {
            "statusCode": status,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Audio file not found", "code": error_code}),
        }


def _serve_image(key: str) -> dict:
    """Return a 307 redirect to a short-lived S3 pre-signed URL for episode artwork."""
    try:
        s3_client.head_object(Bucket=BUCKET_NAME, Key=key)
        url = s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": BUCKET_NAME, "Key": key},
            ExpiresIn=PRESIGN_TTL,
        )
        return {
            "statusCode": 307,
            "headers": {"Location": url, "Cache-Control": "no-store"},
            "body": "",
        }
    except ClientError as exc:
        error_code: str = exc.response["Error"]["Code"]
        logger.error("S3 ClientError fetching image [%s]: %s", error_code, exc)
        status = 404 if error_code in ("404", "NoSuchKey", "NoSuchBucket") else 502
        return {
            "statusCode": status,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Image not found", "code": error_code}),
        }


def lambda_handler(event: dict, context) -> dict:
    """AWS Lambda entry point.

    Routes:
      GET /cover          — 307 redirect to podcast cover art.
      GET /audio/{key}    — 307 redirect to audio file.
      GET /images/{key}   — 307 redirect to episode artwork.
      GET /feed           — RSS 2.0 + Apple Podcasts XML feed (default).
    """
    raw_path = event.get("rawPath", "")
    if raw_path.startswith("/audio/"):
        key = _url_unquote(raw_path[len("/audio/"):])
        return _serve_audio(key)
    if raw_path.startswith("/images/"):
        # S3 key mirrors the URL path: /images/3.jpg → images/3.jpg
        key = "images/" + _url_unquote(raw_path[len("/images/"):])
        return _serve_image(key)
    if raw_path.rstrip("/") == "/cover":
        return _serve_cover()

    try:
        paginator = s3_client.get_paginator("list_objects_v2")
        pages = paginator.paginate(Bucket=BUCKET_NAME)

        audio_items: list[dict] = []
        for page in pages:
            for obj in page.get("Contents", []):
                key: str = obj["Key"]
                if not _is_audio_file(key):
                    continue
                audio_items.append(
                    {
                        "key": key,
                        # Percent-encode the key so spaces and non-ASCII chars
                        # (e.g. Cyrillic filenames) produce a valid URL.
                        "url": f"{PODCAST_LINK}/audio/{_url_quote(key, safe='')}",
                        "size": obj["Size"],
                        "pub_date": _format_pubdate(obj["LastModified"]),
                        "content_type": _get_content_type(key),
                    }
                )

        audio_items.sort(key=lambda x: x["pub_date"], reverse=True)
        rss_xml = _build_rss_feed(audio_items)
        logger.info("Generated RSS feed with %d item(s)", len(audio_items))

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/rss+xml; charset=utf-8",
                "Cache-Control": "public, max-age=300",
            },
            "body": rss_xml,
        }

    except ClientError as exc:
        error_code: str = exc.response["Error"]["Code"]
        logger.error("S3 ClientError [%s]: %s", error_code, exc)
        status = 404 if error_code == "NoSuchBucket" else 502
        return {
            "statusCode": status,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(
                {"error": "Failed to retrieve audio files", "code": error_code}
            ),
        }

    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("Unexpected error: %s", exc)
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Internal server error"}),
        }

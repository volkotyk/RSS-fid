"""
Unit tests for src/handler.py — 100 % branch coverage requirement.

Fixtures are defined in conftest.py.  All S3 calls are intercepted by moto
via mock_aws(); no real AWS traffic is made.
"""
import json
import os
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from unittest.mock import patch

import boto3
import pytest
from botocore.exceptions import ClientError
from moto import mock_aws

import handler  # conftest.py sets env vars before this import

BUCKET    = os.environ["BUCKET_NAME"]
REGION    = "us-east-1"
ITUNES_NS = "http://www.itunes.com/dtds/podcast-1.0.dtd"


# ─────────────────────────────────────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────────────────────────────────────

def _parse(body: str):
    return ET.fromstring(body)


# ─────────────────────────────────────────────────────────────────────────────
# Happy-path tests
# ─────────────────────────────────────────────────────────────────────────────

class TestSuccessfulFeed:
    def test_status_200(self, s3_with_audio):
        result = handler.lambda_handler({}, None)
        assert result["statusCode"] == 200

    def test_content_type_header(self, s3_with_audio):
        result = handler.lambda_handler({}, None)
        assert "application/rss+xml" in result["headers"]["Content-Type"]
        assert "utf-8" in result["headers"]["Content-Type"]

    def test_cache_control_header(self, s3_with_audio):
        result = handler.lambda_handler({}, None)
        assert result["headers"]["Cache-Control"] == "public, max-age=300"

    def test_xml_is_well_formed(self, s3_with_audio):
        result = handler.lambda_handler({}, None)
        root = _parse(result["body"])
        assert root.tag == "rss"

    def test_rss_version_attribute(self, s3_with_audio):
        result = handler.lambda_handler({}, None)
        assert _parse(result["body"]).attrib["version"] == "2.0"

    def test_xml_declaration_present(self, s3_with_audio):
        result = handler.lambda_handler({}, None)
        assert result["body"].startswith("<?xml version")

    def test_itunes_namespace_on_root_element(self, s3_with_audio):
        result = handler.lambda_handler({}, None)
        # The xmlns:itunes declaration must be on the <rss> root tag itself.
        rss_line = next(l for l in result["body"].splitlines() if "<rss " in l)
        assert "xmlns:itunes" in rss_line

    def test_content_namespace_on_root_element(self, s3_with_audio):
        result = handler.lambda_handler({}, None)
        rss_line = next(l for l in result["body"].splitlines() if "<rss " in l)
        assert "xmlns:content" in rss_line

    def test_channel_title_matches_env(self, s3_with_audio):
        result = handler.lambda_handler({}, None)
        assert _parse(result["body"]).find("channel/title").text == "Test Podcast"

    def test_channel_description_matches_env(self, s3_with_audio):
        result = handler.lambda_handler({}, None)
        channel = _parse(result["body"]).find("channel")
        assert channel.find("description").text == "Test Description"

    def test_channel_link_matches_env(self, s3_with_audio):
        result = handler.lambda_handler({}, None)
        channel = _parse(result["body"]).find("channel")
        assert channel.find("link").text == "https://feed.test.example.com"

    def test_channel_language_matches_env(self, s3_with_audio):
        result = handler.lambda_handler({}, None)
        channel = _parse(result["body"]).find("channel")
        assert channel.find("language").text == os.environ["PODCAST_LANGUAGE"]

    def test_itunes_author_in_channel(self, s3_with_audio):
        result = handler.lambda_handler({}, None)
        channel = _parse(result["body"]).find("channel")
        assert channel.find(f"{{{ITUNES_NS}}}author").text == "Test Author"

    def test_itunes_summary_matches_description(self, s3_with_audio):
        result = handler.lambda_handler({}, None)
        channel = _parse(result["body"]).find("channel")
        assert channel.find(f"{{{ITUNES_NS}}}summary").text == "Test Description"

    def test_itunes_explicit_is_false(self, s3_with_audio):
        result = handler.lambda_handler({}, None)
        channel = _parse(result["body"]).find("channel")
        assert channel.find(f"{{{ITUNES_NS}}}explicit").text == "false"

    def test_itunes_image_href_starts_with_https(self, s3_with_audio):
        result = handler.lambda_handler({}, None)
        channel = _parse(result["body"]).find("channel")
        img = channel.find(f"{{{ITUNES_NS}}}image")
        assert img is not None
        assert img.attrib.get("href", "").startswith("https://")

    def test_itunes_category_text_attribute(self, s3_with_audio):
        result = handler.lambda_handler({}, None)
        channel = _parse(result["body"]).find("channel")
        cat = channel.find(f"{{{ITUNES_NS}}}category")
        assert cat is not None
        assert cat.attrib.get("text") == "Education"

    def test_itunes_owner_has_name_and_email(self, s3_with_audio):
        result = handler.lambda_handler({}, None)
        channel = _parse(result["body"]).find("channel")
        owner = channel.find(f"{{{ITUNES_NS}}}owner")
        assert owner is not None
        assert owner.find(f"{{{ITUNES_NS}}}name") is not None
        assert owner.find(f"{{{ITUNES_NS}}}email") is not None

    def test_only_audio_files_included(self, s3_with_audio):
        result = handler.lambda_handler({}, None)
        items = _parse(result["body"]).findall("channel/item")
        # 4 audio files uploaded (mp3, mp3, wav, m4a); 2 non-audio excluded
        assert len(items) == 4

    def test_jpg_excluded_from_feed(self, s3_with_audio):
        result = handler.lambda_handler({}, None)
        titles = {i.find("title").text for i in _parse(result["body"]).findall("channel/item")}
        assert "cover-art" not in titles

    def test_txt_excluded_from_feed(self, s3_with_audio):
        result = handler.lambda_handler({}, None)
        titles = {i.find("title").text for i in _parse(result["body"]).findall("channel/item")}
        assert "notes" not in titles

    def test_enclosure_has_required_attributes(self, s3_with_audio):
        result = handler.lambda_handler({}, None)
        enc = _parse(result["body"]).find("channel/item/enclosure")
        assert enc is not None
        assert "url" in enc.attrib
        assert "length" in enc.attrib
        assert "type" in enc.attrib

    def test_mp3_enclosure_type(self, s3_bucket):
        s3_bucket.put_object(Bucket=BUCKET, Key="ep.mp3", Body=b"x" * 1000)
        result = handler.lambda_handler({}, None)
        enc = _parse(result["body"]).find("channel/item/enclosure")
        assert enc.attrib["type"] == "audio/mpeg"

    def test_wav_enclosure_type(self, s3_bucket):
        s3_bucket.put_object(Bucket=BUCKET, Key="ep.wav", Body=b"x" * 1000)
        result = handler.lambda_handler({}, None)
        enc = _parse(result["body"]).find("channel/item/enclosure")
        assert enc.attrib["type"] == "audio/wav"

    def test_m4a_enclosure_type(self, s3_bucket):
        s3_bucket.put_object(Bucket=BUCKET, Key="ep.m4a", Body=b"x" * 1000)
        result = handler.lambda_handler({}, None)
        enc = _parse(result["body"]).find("channel/item/enclosure")
        assert enc.attrib["type"] == "audio/mp4"

    def test_aac_enclosure_type(self, s3_bucket):
        s3_bucket.put_object(Bucket=BUCKET, Key="ep.aac", Body=b"x" * 1000)
        result = handler.lambda_handler({}, None)
        enc = _parse(result["body"]).find("channel/item/enclosure")
        assert enc.attrib["type"] == "audio/aac"

    def test_ogg_enclosure_type(self, s3_bucket):
        s3_bucket.put_object(Bucket=BUCKET, Key="ep.ogg", Body=b"x" * 1000)
        result = handler.lambda_handler({}, None)
        enc = _parse(result["body"]).find("channel/item/enclosure")
        assert enc.attrib["type"] == "audio/ogg"

    def test_flac_enclosure_type(self, s3_bucket):
        s3_bucket.put_object(Bucket=BUCKET, Key="ep.flac", Body=b"x" * 1000)
        result = handler.lambda_handler({}, None)
        enc = _parse(result["body"]).find("channel/item/enclosure")
        assert enc.attrib["type"] == "audio/flac"

    def test_enclosure_length_matches_object_size(self, s3_bucket):
        payload = b"z" * 98_765
        s3_bucket.put_object(Bucket=BUCKET, Key="ep.mp3", Body=payload)
        result = handler.lambda_handler({}, None)
        enc = _parse(result["body"]).find("channel/item/enclosure")
        assert enc.attrib["length"] == "98765"

    def test_enclosure_url_contains_key(self, s3_bucket):
        s3_bucket.put_object(Bucket=BUCKET, Key="ep.mp3", Body=b"data")
        result = handler.lambda_handler({}, None)
        enc = _parse(result["body"]).find("channel/item/enclosure")
        assert "ep.mp3" in enc.attrib["url"]

    def test_enclosure_url_percent_encodes_spaces(self, s3_bucket):
        s3_bucket.put_object(Bucket=BUCKET, Key="my episode.mp3", Body=b"data")
        result = handler.lambda_handler({}, None)
        enc = _parse(result["body"]).find("channel/item/enclosure")
        assert "my%20episode.mp3" in enc.attrib["url"]
        assert " " not in enc.attrib["url"]

    def test_enclosure_url_percent_encodes_unicode(self, s3_bucket):
        s3_bucket.put_object(Bucket=BUCKET, Key="епізод.mp3", Body=b"data")
        result = handler.lambda_handler({}, None)
        enc = _parse(result["body"]).find("channel/item/enclosure")
        assert "%" in enc.attrib["url"]
        assert "епізод" not in enc.attrib["url"]

    def test_guid_equals_s3_key(self, s3_bucket):
        s3_bucket.put_object(Bucket=BUCKET, Key="my-ep.mp3", Body=b"data")
        result = handler.lambda_handler({}, None)
        guid = _parse(result["body"]).find("channel/item/guid")
        assert guid.text == "my-ep.mp3"

    def test_guid_is_not_permalink(self, s3_bucket):
        s3_bucket.put_object(Bucket=BUCKET, Key="ep.mp3", Body=b"data")
        result = handler.lambda_handler({}, None)
        guid = _parse(result["body"]).find("channel/item/guid")
        assert guid.attrib.get("isPermaLink") == "false"

    def test_pubdate_is_non_empty(self, s3_bucket):
        s3_bucket.put_object(Bucket=BUCKET, Key="ep.mp3", Body=b"data")
        result = handler.lambda_handler({}, None)
        pub = _parse(result["body"]).find("channel/item/pubDate")
        assert pub is not None and pub.text

    def test_item_title_strips_extension(self, s3_bucket):
        s3_bucket.put_object(Bucket=BUCKET, Key="episode-007.mp3", Body=b"data")
        result = handler.lambda_handler({}, None)
        title = _parse(result["body"]).find("channel/item/title")
        assert title.text == "episode-007"

    def test_item_has_description(self, s3_bucket):
        s3_bucket.put_object(Bucket=BUCKET, Key="episode-007.mp3", Body=b"data")
        result = handler.lambda_handler({}, None)
        desc = _parse(result["body"]).find("channel/item/description")
        assert desc is not None and desc.text == "episode-007"

    def test_numbered_item_has_itunes_image_in_feed(self, s3_bucket):
        s3_bucket.put_object(Bucket=BUCKET, Key="3. Episode.mp3", Body=b"data")
        result = handler.lambda_handler({}, None)
        item = _parse(result["body"]).find("channel/item")
        img = item.find(f"{{{ITUNES_NS}}}image")
        assert img is not None
        assert "images/3.png" in img.attrib["href"]

    def test_itunes_namespace_in_output(self, s3_bucket):
        s3_bucket.put_object(Bucket=BUCKET, Key="ep.mp3", Body=b"data")
        result = handler.lambda_handler({}, None)
        assert "itunes" in result["body"]


# ─────────────────────────────────────────────────────────────────────────────
# Cover-art endpoint  (GET /cover)
# ─────────────────────────────────────────────────────────────────────────────

class TestCoverEndpoint:
    def test_cover_returns_307(self, s3_bucket):
        s3_bucket.put_object(Bucket=BUCKET, Key="images/cover.png", Body=b"fake-png")
        result = handler.lambda_handler({"rawPath": "/cover"}, None)
        assert result["statusCode"] == 307

    def test_cover_location_header_present(self, s3_bucket):
        s3_bucket.put_object(Bucket=BUCKET, Key="images/cover.png", Body=b"fake-png")
        result = handler.lambda_handler({"rawPath": "/cover"}, None)
        assert "Location" in result["headers"]

    def test_cover_location_contains_s3_host(self, s3_bucket):
        s3_bucket.put_object(Bucket=BUCKET, Key="images/cover.png", Body=b"fake-png")
        result = handler.lambda_handler({"rawPath": "/cover"}, None)
        assert "amazonaws.com" in result["headers"]["Location"]

    def test_cover_location_contains_key(self, s3_bucket):
        s3_bucket.put_object(Bucket=BUCKET, Key="images/cover.png", Body=b"fake-png")
        result = handler.lambda_handler({"rawPath": "/cover"}, None)
        assert "cover.png" in result["headers"]["Location"]

    def test_cover_cache_control_no_store(self, s3_bucket):
        s3_bucket.put_object(Bucket=BUCKET, Key="images/cover.png", Body=b"fake-png")
        result = handler.lambda_handler({"rawPath": "/cover"}, None)
        assert result["headers"]["Cache-Control"] == "no-store"

    def test_cover_trailing_slash_also_routes(self, s3_bucket):
        s3_bucket.put_object(Bucket=BUCKET, Key="images/cover.png", Body=b"fake-png")
        result = handler.lambda_handler({"rawPath": "/cover/"}, None)
        assert result["statusCode"] == 307

    def test_no_raw_path_returns_feed(self, s3_bucket):
        # Empty event (no rawPath) falls through to RSS feed, not cover.
        result = handler.lambda_handler({}, None)
        assert result["statusCode"] == 200
        assert "application/rss+xml" in result["headers"]["Content-Type"]

    def test_cover_missing_key_returns_404(self, s3_bucket):
        # cover.png not uploaded — should return 404
        result = handler.lambda_handler({"rawPath": "/cover"}, None)
        assert result["statusCode"] == 404

    def test_cover_missing_key_returns_json(self, s3_bucket):
        result = handler.lambda_handler({"rawPath": "/cover"}, None)
        body = json.loads(result["body"])
        assert "error" in body

    def test_cover_no_such_bucket_returns_404(self, aws_mock):
        result = handler.lambda_handler({"rawPath": "/cover"}, None)
        assert result["statusCode"] == 404

    def test_cover_access_denied_returns_502(self, s3_bucket):
        err = {"Error": {"Code": "AccessDenied", "Message": "Denied"}}
        with patch.object(
            handler.s3_client,
            "head_object",
            side_effect=ClientError(err, "HeadObject"),
        ):
            result = handler.lambda_handler({"rawPath": "/cover"}, None)
        assert result["statusCode"] == 502


# ─────────────────────────────────────────────────────────────────────────────
# Audio endpoint  (GET /audio/{key})
# ─────────────────────────────────────────────────────────────────────────────

class TestAudioEndpoint:
    def test_audio_returns_307(self, s3_bucket):
        s3_bucket.put_object(Bucket=BUCKET, Key="ep.mp3", Body=b"data")
        result = handler.lambda_handler({"rawPath": "/audio/ep.mp3"}, None)
        assert result["statusCode"] == 307

    def test_audio_location_header_present(self, s3_bucket):
        s3_bucket.put_object(Bucket=BUCKET, Key="ep.mp3", Body=b"data")
        result = handler.lambda_handler({"rawPath": "/audio/ep.mp3"}, None)
        assert "Location" in result["headers"]

    def test_audio_location_contains_s3_host(self, s3_bucket):
        s3_bucket.put_object(Bucket=BUCKET, Key="ep.mp3", Body=b"data")
        result = handler.lambda_handler({"rawPath": "/audio/ep.mp3"}, None)
        assert "amazonaws.com" in result["headers"]["Location"]

    def test_audio_cache_control_no_store(self, s3_bucket):
        s3_bucket.put_object(Bucket=BUCKET, Key="ep.mp3", Body=b"data")
        result = handler.lambda_handler({"rawPath": "/audio/ep.mp3"}, None)
        assert result["headers"]["Cache-Control"] == "no-store"

    def test_audio_url_decoded_key_resolves(self, s3_bucket):
        # rawPath arrives percent-encoded; handler must decode it to find the key.
        s3_bucket.put_object(Bucket=BUCKET, Key="my episode.mp3", Body=b"data")
        result = handler.lambda_handler({"rawPath": "/audio/my%20episode.mp3"}, None)
        assert result["statusCode"] == 307

    def test_audio_missing_key_returns_404(self, s3_bucket):
        result = handler.lambda_handler({"rawPath": "/audio/missing.mp3"}, None)
        assert result["statusCode"] == 404

    def test_audio_missing_key_returns_json(self, s3_bucket):
        result = handler.lambda_handler({"rawPath": "/audio/missing.mp3"}, None)
        assert "error" in json.loads(result["body"])

    def test_audio_no_such_bucket_returns_404(self, aws_mock):
        result = handler.lambda_handler({"rawPath": "/audio/ep.mp3"}, None)
        assert result["statusCode"] == 404

    def test_audio_access_denied_returns_502(self, s3_bucket):
        err = {"Error": {"Code": "AccessDenied", "Message": "Denied"}}
        with patch.object(
            handler.s3_client,
            "head_object",
            side_effect=ClientError(err, "HeadObject"),
        ):
            result = handler.lambda_handler({"rawPath": "/audio/ep.mp3"}, None)
        assert result["statusCode"] == 502


# ─────────────────────────────────────────────────────────────────────────────
# Image endpoint  (GET /images/{key})
# ─────────────────────────────────────────────────────────────────────────────

class TestImageEndpoint:
    def test_image_returns_307(self, s3_bucket):
        s3_bucket.put_object(Bucket=BUCKET, Key="images/3.png", Body=b"fake-png")
        result = handler.lambda_handler({"rawPath": "/images/3.png"}, None)
        assert result["statusCode"] == 307

    def test_image_location_contains_s3_host(self, s3_bucket):
        s3_bucket.put_object(Bucket=BUCKET, Key="images/3.png", Body=b"fake-png")
        result = handler.lambda_handler({"rawPath": "/images/3.png"}, None)
        assert "amazonaws.com" in result["headers"]["Location"]

    def test_image_cache_control_no_store(self, s3_bucket):
        s3_bucket.put_object(Bucket=BUCKET, Key="images/3.png", Body=b"fake-png")
        result = handler.lambda_handler({"rawPath": "/images/3.png"}, None)
        assert result["headers"]["Cache-Control"] == "no-store"

    def test_image_missing_returns_404(self, s3_bucket):
        result = handler.lambda_handler({"rawPath": "/images/99.jpg"}, None)
        assert result["statusCode"] == 404

    def test_image_missing_returns_json(self, s3_bucket):
        result = handler.lambda_handler({"rawPath": "/images/99.jpg"}, None)
        assert "error" in json.loads(result["body"])

    def test_image_no_such_bucket_returns_404(self, aws_mock):
        result = handler.lambda_handler({"rawPath": "/images/3.png"}, None)
        assert result["statusCode"] == 404

    def test_image_access_denied_returns_502(self, s3_bucket):
        err = {"Error": {"Code": "AccessDenied", "Message": "Denied"}}
        with patch.object(
            handler.s3_client,
            "head_object",
            side_effect=ClientError(err, "HeadObject"),
        ):
            result = handler.lambda_handler({"rawPath": "/images/3.png"}, None)
        assert result["statusCode"] == 502


# ─────────────────────────────────────────────────────────────────────────────
# Empty / no-audio bucket
# ─────────────────────────────────────────────────────────────────────────────

class TestEmptyBucket:
    def test_empty_bucket_returns_200(self, s3_bucket):
        result = handler.lambda_handler({}, None)
        assert result["statusCode"] == 200

    def test_empty_bucket_returns_valid_rss(self, s3_bucket):
        result = handler.lambda_handler({}, None)
        root = _parse(result["body"])
        assert root.tag == "rss"

    def test_empty_bucket_has_zero_items(self, s3_bucket):
        result = handler.lambda_handler({}, None)
        assert len(_parse(result["body"]).findall("channel/item")) == 0

    def test_non_audio_only_bucket_has_zero_items(self, s3_bucket):
        s3_bucket.put_object(Bucket=BUCKET, Key="image.png", Body=b"img")
        s3_bucket.put_object(Bucket=BUCKET, Key="README.md", Body=b"text")
        result = handler.lambda_handler({}, None)
        assert len(_parse(result["body"]).findall("channel/item")) == 0


# ─────────────────────────────────────────────────────────────────────────────
# S3 error scenarios
# ─────────────────────────────────────────────────────────────────────────────

class TestErrorHandling:
    def test_no_such_bucket_returns_404(self, aws_mock):
        # aws_mock activates moto but creates no bucket
        result = handler.lambda_handler({}, None)
        assert result["statusCode"] == 404

    def test_no_such_bucket_returns_json(self, aws_mock):
        result = handler.lambda_handler({}, None)
        body = json.loads(result["body"])
        assert "error" in body

    def test_no_such_bucket_error_code_in_body(self, aws_mock):
        result = handler.lambda_handler({}, None)
        body = json.loads(result["body"])
        assert "NoSuchBucket" in body.get("code", "")

    def test_access_denied_returns_502(self, s3_bucket):
        err = {"Error": {"Code": "AccessDenied", "Message": "Access Denied"}}
        with patch.object(
            handler.s3_client,
            "get_paginator",
            side_effect=ClientError(err, "ListObjectsV2"),
        ):
            result = handler.lambda_handler({}, None)
        assert result["statusCode"] == 502

    def test_access_denied_content_type_json(self, s3_bucket):
        err = {"Error": {"Code": "AccessDenied", "Message": "Access Denied"}}
        with patch.object(
            handler.s3_client,
            "get_paginator",
            side_effect=ClientError(err, "ListObjectsV2"),
        ):
            result = handler.lambda_handler({}, None)
        assert result["headers"]["Content-Type"] == "application/json"

    def test_unexpected_exception_returns_500(self, s3_bucket):
        with patch.object(
            handler.s3_client,
            "get_paginator",
            side_effect=RuntimeError("disk on fire"),
        ):
            result = handler.lambda_handler({}, None)
        assert result["statusCode"] == 500

    def test_unexpected_exception_body_has_error_key(self, s3_bucket):
        with patch.object(
            handler.s3_client,
            "get_paginator",
            side_effect=RuntimeError("disk on fire"),
        ):
            result = handler.lambda_handler({}, None)
        assert "error" in json.loads(result["body"])


# ─────────────────────────────────────────────────────────────────────────────
# Helper function unit tests
# ─────────────────────────────────────────────────────────────────────────────

class TestIsAudioFile:
    @pytest.mark.parametrize("key", ["ep.mp3", "ep.wav", "ep.m4a", "ep.aac", "ep.ogg", "ep.flac"])
    def test_audio_extensions_accepted(self, key):
        assert handler._is_audio_file(key) is True

    @pytest.mark.parametrize("key", ["cover.jpg", "notes.txt", "data.json", "README.md"])
    def test_non_audio_extensions_rejected(self, key):
        assert handler._is_audio_file(key) is False

    def test_case_insensitive_mp3(self):
        assert handler._is_audio_file("Episode.MP3") is True

    def test_case_insensitive_wav(self):
        assert handler._is_audio_file("Episode.WAV") is True


class TestGetContentType:
    def test_mp3_returns_audio_mpeg(self):
        assert handler._get_content_type("ep.mp3") == "audio/mpeg"

    def test_wav_returns_audio_wav(self):
        assert handler._get_content_type("ep.wav") == "audio/wav"

    def test_m4a_returns_audio_mp4(self):
        assert handler._get_content_type("ep.m4a") == "audio/mp4"

    def test_aac_returns_audio_aac(self):
        assert handler._get_content_type("ep.aac") == "audio/aac"

    def test_ogg_returns_audio_ogg(self):
        assert handler._get_content_type("ep.ogg") == "audio/ogg"

    def test_flac_returns_audio_flac(self):
        assert handler._get_content_type("ep.flac") == "audio/flac"

    def test_unknown_extension_defaults_to_audio_mpeg(self):
        assert handler._get_content_type("ep.xyz") == "audio/mpeg"

    def test_case_insensitive(self):
        assert handler._get_content_type("ep.MP3") == "audio/mpeg"


class TestFormatPubdate:
    def test_returns_string(self):
        dt = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        assert isinstance(handler._format_pubdate(dt), str)

    def test_contains_year(self):
        dt = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        assert "2024" in handler._format_pubdate(dt)

    def test_contains_month_abbreviation(self):
        dt = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        assert "Jun" in handler._format_pubdate(dt)

    def test_contains_gmt(self):
        dt = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        assert "GMT" in handler._format_pubdate(dt)

    def test_naive_datetime_treated_as_utc(self):
        dt_naive = datetime(2024, 6, 15, 12, 0, 0)
        result = handler._format_pubdate(dt_naive)
        assert "2024" in result


class TestItemImageKey:
    def test_numbered_prefix_returns_jpg_key(self):
        assert handler._item_image_key("3. Справжня.m4a") == "images/3.png"

    def test_zero_prefix(self):
        assert handler._item_image_key("0. Intro.mp3") == "images/0.png"

    def test_multi_digit_prefix(self):
        assert handler._item_image_key("9. discover-canada.mp3") == "images/9.png"

    def test_no_numeric_prefix_returns_none(self):
        assert handler._item_image_key("episode-007.mp3") is None

    def test_letter_prefix_returns_none(self):
        assert handler._item_image_key("bonus.mp3") is None


class TestItemTitle:
    def test_strips_mp3_extension(self):
        assert handler._item_title("episode.mp3") == "episode"

    def test_strips_m4a_extension(self):
        assert handler._item_title("bonus.m4a") == "bonus"

    def test_preserves_dots_in_name(self):
        # os.path.splitext splits on the LAST dot only
        assert handler._item_title("ep.1.mp3") == "ep.1"

    def test_no_extension_unchanged(self):
        assert handler._item_title("episode") == "episode"


class TestBuildRssFeed:
    def test_empty_list_returns_valid_rss(self):
        xml_str = handler._build_rss_feed([])
        root = ET.fromstring(xml_str)
        assert root.tag == "rss"

    def test_empty_list_has_no_items(self):
        xml_str = handler._build_rss_feed([])
        assert len(ET.fromstring(xml_str).findall("channel/item")) == 0

    def test_single_item_present(self):
        items = [{
            "key": "ep.mp3",
            "url": "https://feed.test.example.com/audio/ep.mp3",
            "size": 1000,
            "pub_date": "Mon, 01 Jan 2024 00:00:00 GMT",
            "content_type": "audio/mpeg",
        }]
        root = ET.fromstring(handler._build_rss_feed(items))
        assert len(root.findall("channel/item")) == 1

    def test_itunes_namespace_in_output(self):
        xml_str = handler._build_rss_feed([])
        assert handler.ITUNES_NS in xml_str

    def test_content_namespace_in_output(self):
        xml_str = handler._build_rss_feed([])
        assert handler.CONTENT_NS in xml_str

    def test_namespaces_on_root_rss_element(self):
        xml_str = handler._build_rss_feed([])
        rss_line = next(l for l in xml_str.splitlines() if "<rss " in l)
        assert "xmlns:itunes" in rss_line
        assert "xmlns:content" in rss_line

    def test_xml_declaration_present(self):
        xml_str = handler._build_rss_feed([])
        assert xml_str.startswith("<?xml version")

    def test_channel_has_itunes_summary(self):
        xml_str = handler._build_rss_feed([])
        channel = ET.fromstring(xml_str).find("channel")
        assert channel.find(f"{{{handler.ITUNES_NS}}}summary") is not None

    def test_channel_has_itunes_image(self):
        xml_str = handler._build_rss_feed([])
        channel = ET.fromstring(xml_str).find("channel")
        assert channel.find(f"{{{handler.ITUNES_NS}}}image") is not None

    def test_channel_has_itunes_category(self):
        xml_str = handler._build_rss_feed([])
        channel = ET.fromstring(xml_str).find("channel")
        assert channel.find(f"{{{handler.ITUNES_NS}}}category") is not None

    def test_channel_has_itunes_owner(self):
        xml_str = handler._build_rss_feed([])
        channel = ET.fromstring(xml_str).find("channel")
        assert channel.find(f"{{{handler.ITUNES_NS}}}owner") is not None

    def test_numbered_item_has_itunes_image(self):
        items = [{
            "key": "3. Episode.mp3",
            "url": "https://feed.test.example.com/audio/3.%20Episode.mp3",
            "size": 1000,
            "pub_date": "Mon, 01 Jan 2024 00:00:00 GMT",
            "content_type": "audio/mpeg",
        }]
        root = ET.fromstring(handler._build_rss_feed(items))
        img = root.find(f"channel/item/{{{handler.ITUNES_NS}}}image")
        assert img is not None
        assert "images/3.png" in img.attrib["href"]

    def test_unnumbered_item_has_no_itunes_image(self):
        items = [{
            "key": "bonus.mp3",
            "url": "https://feed.test.example.com/audio/bonus.mp3",
            "size": 1000,
            "pub_date": "Mon, 01 Jan 2024 00:00:00 GMT",
            "content_type": "audio/mpeg",
        }]
        root = ET.fromstring(handler._build_rss_feed(items))
        assert root.find(f"channel/item/{{{handler.ITUNES_NS}}}image") is None

    def test_item_duration_defaults_to_zero(self):
        items = [{
            "key": "ep.mp3",
            "url": "https://feed.test.example.com/audio/ep.mp3",
            "size": 1000,
            "pub_date": "Mon, 01 Jan 2024 00:00:00 GMT",
            "content_type": "audio/mpeg",
            # no "duration" key — should default to "0"
        }]
        root = ET.fromstring(handler._build_rss_feed(items))
        dur = root.find(f"channel/item/{{{handler.ITUNES_NS}}}duration")
        assert dur is not None and dur.text == "0"

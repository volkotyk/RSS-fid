"""
Set environment variables and fake AWS credentials BEFORE handler is imported.
pytest guarantees conftest.py runs before test module collection, so module-level
constants in handler.py will see these values.
"""
import os

import pytest
import boto3
from moto import mock_aws

# Fake credentials prevent accidental real-AWS calls if moto ever fails to intercept
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("AWS_SECURITY_TOKEN", "testing")
os.environ.setdefault("AWS_SESSION_TOKEN", "testing")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

os.environ["BUCKET_NAME"]         = "test-podcast-bucket"
os.environ["PODCAST_TITLE"]       = "Test Podcast"
os.environ["PODCAST_DESCRIPTION"] = "Test Description"
os.environ["PODCAST_AUTHOR"]      = "Test Author"
os.environ["PODCAST_LINK"]        = "https://feed.test.example.com"
os.environ["PODCAST_LANGUAGE"]    = "uk"
os.environ["PODCAST_IMAGE_URL"]   = "https://example.com/podcast-cover.jpg"
os.environ["PODCAST_CATEGORY"]    = "Education"
os.environ["PODCAST_OWNER_NAME"]  = "Test Owner"
os.environ["PODCAST_OWNER_EMAIL"] = "test@example.com"

BUCKET = os.environ["BUCKET_NAME"]
REGION = "us-east-1"


@pytest.fixture
def aws_mock():
    """Activate moto — no bucket created. Use for error-scenario tests."""
    with mock_aws():
        yield boto3.client("s3", region_name=REGION)


@pytest.fixture
def s3_bucket(aws_mock):
    """Empty mocked S3 bucket."""
    aws_mock.create_bucket(Bucket=BUCKET)
    yield aws_mock


@pytest.fixture
def s3_with_audio(s3_bucket):
    """Bucket pre-loaded with a mix of audio and non-audio objects."""
    audio_and_non_audio = [
        ("episode-001.mp3", b"a" * (1024 * 1024)),        # 1 MB mp3
        ("episode-002.mp3", b"b" * (2 * 1024 * 1024)),    # 2 MB mp3
        ("episode-003.wav", b"c" * (4 * 1024 * 1024)),    # 4 MB wav
        ("bonus.m4a", b"d" * 512_000),                    # m4a
        ("cover-art.jpg", b"e" * (50 * 1024)),             # excluded
        ("notes.txt", b"f" * 512),                         # excluded
    ]
    for key, body in audio_and_non_audio:
        s3_bucket.put_object(Bucket=BUCKET, Key=key, Body=body)
    yield s3_bucket

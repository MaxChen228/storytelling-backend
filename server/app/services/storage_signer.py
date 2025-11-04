"""Helpers for generating signed URLs for Google Cloud Storage objects."""

from __future__ import annotations

from datetime import timedelta
from typing import Optional

from google.cloud import storage

from .gcs_mirror import parse_gcs_uri


def generate_signed_url(
    gcs_uri: str,
    expires_in_seconds: int,
    *,
    response_content_type: Optional[str] = None,
    response_disposition: Optional[str] = None,
    method: str = "GET",
) -> str:
    """Return a V4 signed URL for the given ``gs://`` URI."""

    bucket_name, object_path = parse_gcs_uri(gcs_uri)
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(object_path)

    params = {}
    if response_content_type:
        params["response_content_type"] = response_content_type
    if response_disposition:
        params["response_disposition"] = response_disposition

    return blob.generate_signed_url(
        version="v4",
        expiration=timedelta(seconds=max(60, int(expires_in_seconds))),
        method=method,
        **params,
    )

"""Helpers for generating signed URLs for Google Cloud Storage objects."""

from __future__ import annotations

from datetime import timedelta
from typing import Optional

from google.auth import iam
from google.auth.transport import requests
from google.cloud import storage
from google.oauth2 import service_account

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
    base_credentials = getattr(client, "_credentials", None)
    request = requests.Request()
    if base_credentials is not None:
        if hasattr(base_credentials, "with_scopes"):
            base_credentials = base_credentials.with_scopes(
                [
                    "https://www.googleapis.com/auth/cloud-platform",
                    "https://www.googleapis.com/auth/iam",
                ]
            )
        try:
            base_credentials.refresh(request)
        except Exception:
            pass

    bucket = client.bucket(bucket_name)
    blob = bucket.blob(object_path)
    signer_email: Optional[str]
    try:
        signer_email = client.get_service_account_email()
    except AttributeError:
        signer_email = None

    params = {}
    if response_content_type:
        params["response_type"] = response_content_type
    if response_disposition:
        params["response_disposition"] = response_disposition

    signing_credentials = None
    if signer_email and base_credentials:
        signer = iam.Signer(request, base_credentials, signer_email)
        token_uri = getattr(base_credentials, "token_uri", "https://oauth2.googleapis.com/token")
        signing_credentials = service_account.Credentials(  # type: ignore[arg-type]
            signer=signer,
            service_account_email=signer_email,
            token_uri=token_uri,
        )

    return blob.generate_signed_url(
        version="v4",
        expiration=timedelta(seconds=max(60, int(expires_in_seconds))),
        method=method,
        service_account_email=signer_email,
        credentials=signing_credentials or base_credentials,
        **params,
    )

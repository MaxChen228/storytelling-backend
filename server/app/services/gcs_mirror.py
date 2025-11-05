"""
Helpers to mirror a Google Cloud Storage prefix into a local directory.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import timezone
from pathlib import Path
import os
from typing import Dict, Optional, Set, Tuple

from google.cloud import storage

logger = logging.getLogger(__name__)


def is_gcs_uri(value: str) -> bool:
    return value.startswith("gs://")


def parse_gcs_uri(uri: str) -> Tuple[str, str]:
    if not is_gcs_uri(uri):
        raise ValueError(f"Unsupported GCS URI: {uri}")
    body = uri[len("gs://") :]
    if "/" not in body:
        return body, ""
    bucket, prefix = body.split("/", 1)
    return bucket, prefix.rstrip("/")


def _load_manifest(path: Path) -> Dict[str, Dict[str, str]]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # pragma: no cover - corrupted manifest is rare
        logger.warning("Failed to read manifest %s, rebuilding.", path)
        return {}


@dataclass
class GCSMirror:
    gcs_uri: str
    local_dir: Path
    client: Optional[storage.Client] = None
    manifest_path: Optional[Path] = None
    download_suffixes: Optional[Set[str]] = None

    def __post_init__(self) -> None:
        self.bucket_name, self.prefix = parse_gcs_uri(self.gcs_uri)
        self.local_dir = self.local_dir.resolve()
        if self.manifest_path is None:
            self.manifest_path = self.local_dir / ".gcs_manifest.json"
        if self.client is None:
            self.client = storage.Client()
        self._manifest: Dict[str, Dict[str, str]] = _load_manifest(self.manifest_path)
        if self.download_suffixes:
            self.download_suffixes = {suffix.lower() for suffix in self.download_suffixes}

    def sync(self) -> None:
        """Download/update blobs so local folder mirrors the remote prefix."""
        bucket = self.client.bucket(self.bucket_name)

        remote_entries: Dict[str, Dict[str, str]] = {}

        prefix = self.prefix
        list_prefix = prefix + "/" if prefix else None

        logger.info("Syncing GCS prefix %s to %s", self.gcs_uri, self.local_dir)

        self.local_dir.mkdir(parents=True, exist_ok=True)

        for blob in self.client.list_blobs(bucket, prefix=list_prefix):
            rel_path = self._relative_path(blob.name)
            if rel_path is None:
                continue
            if rel_path.endswith("/"):
                continue

            metadata = {
                "etag": blob.etag,
                "generation": str(blob.generation),
                "updated": blob.updated.isoformat() if blob.updated else "",
                "size": str(blob.size),
            }
            remote_entries[rel_path] = metadata

            local_path = self.local_dir / rel_path
            if self.download_suffixes and Path(rel_path).suffix.lower() not in self.download_suffixes:
                # Skip downloading large files but keep manifest entry up to date.
                continue

            if not self._should_download(rel_path, metadata, local_path):
                continue

            local_path.parent.mkdir(parents=True, exist_ok=True)
            logger.info("Downloading gs://%s/%s → %s", self.bucket_name, blob.name, local_path)
            blob.download_to_filename(str(local_path))
            if blob.updated:
                ts = blob.updated
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                mtime = ts.timestamp()
                os.utime(local_path, (mtime, mtime))

        # Remove stale files that no longer exist remotely
        stale_entries = set(self._manifest.keys()) - set(remote_entries.keys())
        for rel_path in stale_entries:
            candidate = self.local_dir / rel_path
            try:
                if candidate.exists():
                    candidate.unlink()
            except OSError:
                logger.warning("Failed to remove stale file %s", candidate)

        self._manifest = remote_entries
        self._write_manifest()

    def get_manifest_entry(self, rel_path: str) -> Optional[Dict[str, str]]:
        key = rel_path.replace("\\", "/")
        return self._manifest.get(key)

    def get_gcs_uri(self, rel_path: str) -> Optional[str]:
        key = rel_path.replace("\\", "/")
        if key not in self._manifest:
            return None
        if self.prefix:
            full_path = f"{self.prefix}/{key}" if key else self.prefix
        else:
            full_path = key
        if full_path:
            return f"gs://{self.bucket_name}/{full_path}"
        return f"gs://{self.bucket_name}"

    def iter_relative_paths(self, prefix: Optional[str] = None) -> Tuple[str, ...]:
        """
        Return cached manifest keys filtered by a relative prefix.

        Args:
            prefix: Relative directory within the mirrored bucket
                (e.g. "book/assets" 或 "book/chapter/assets").
        """
        if not self._manifest:
            return tuple()

        if not prefix:
            return tuple(sorted(self._manifest.keys()))

        normalized = prefix.replace("\\", "/").strip("/")
        if not normalized:
            return tuple(sorted(self._manifest.keys()))

        needle = normalized + "/"
        matched = []
        for key in self._manifest.keys():
            if key == normalized or key.startswith(needle):
                matched.append(key)
        return tuple(sorted(matched))

    # ------------------------------------------------------------------

    def _relative_path(self, blob_name: str) -> Optional[str]:
        if not self.prefix:
            return blob_name
        if blob_name.startswith(self.prefix + "/"):
            return blob_name[len(self.prefix) + 1 :]
        if blob_name == self.prefix:
            return ""
        return None

    def _should_download(self, rel_path: str, metadata: Dict[str, str], local_path: Path) -> bool:
        if not local_path.exists():
            return True
        cached = self._manifest.get(rel_path)
        if not cached:
            return True
        if cached.get("etag") != metadata.get("etag"):
            return True
        if cached.get("generation") != metadata.get("generation"):
            return True

        try:
            local_size = local_path.stat().st_size
        except OSError:
            return True
        remote_size = int(metadata.get("size", "-1"))
        return local_size != remote_size

    def _write_manifest(self) -> None:
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        self.manifest_path.write_text(json.dumps(self._manifest, ensure_ascii=False, indent=2), encoding="utf-8")

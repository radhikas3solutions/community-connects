"""Photo storage: Supabase Storage (private bucket + signed URLs).

Only the API writes to the bucket, using the server-side service-role key. Browsers
never get write access; they only receive short-lived signed URLs for reading.
"""

import logging
from typing import Protocol
from urllib.parse import quote

import httpx2

from app.core.config import Settings

log = logging.getLogger(__name__)


class StorageError(RuntimeError):
    """Storage backend failed."""


class PhotoStorage(Protocol):
    def upload(self, path: str, data: bytes, content_type: str) -> None: ...

    def delete(self, paths: list[str]) -> None: ...

    def signed_urls(self, paths: list[str]) -> dict[str, str]:
        """Map each path to a temporary read URL. Missing objects are omitted."""
        ...


class SupabaseStorage:
    def __init__(self, settings: Settings, client: httpx2.Client | None = None) -> None:
        self._base = f"{settings.supabase_url.rstrip('/')}/storage/v1"
        self._public_base = settings.supabase_url.rstrip("/")
        self._bucket = settings.storage_bucket
        self._ttl = settings.signed_url_ttl_seconds
        key = settings.supabase_service_role_key
        self._client = client or httpx2.Client(
            timeout=20.0,
            headers={"Authorization": f"Bearer {key}", "apikey": key},
        )

    def _object_url(self, path: str) -> str:
        return f"{self._base}/object/{self._bucket}/{quote(path)}"

    def upload(self, path: str, data: bytes, content_type: str) -> None:
        try:
            r = self._client.post(
                self._object_url(path),
                content=data,
                headers={
                    "Content-Type": content_type,
                    "Cache-Control": "max-age=31536000",
                    "x-upsert": "false",
                },
            )
        except httpx2.HTTPError as exc:
            raise StorageError("Upload failed") from exc
        if r.status_code >= 400:
            log.error("storage upload failed: %s %s", r.status_code, r.text[:300])
            raise StorageError("Upload failed")

    def delete(self, paths: list[str]) -> None:
        if not paths:
            return
        try:
            r = self._client.request(
                "DELETE", f"{self._base}/object/{self._bucket}", json={"prefixes": paths}
            )
            if r.status_code >= 400:
                log.warning("storage delete failed: %s %s", r.status_code, r.text[:300])
        except httpx2.HTTPError:
            # Orphaned objects are harmless (private bucket); never fail a request over cleanup.
            log.warning("storage delete failed for %d objects", len(paths), exc_info=True)

    def signed_urls(self, paths: list[str]) -> dict[str, str]:
        if not paths:
            return {}
        try:
            r = self._client.post(
                f"{self._base}/object/sign/{self._bucket}",
                json={"expiresIn": self._ttl, "paths": paths},
            )
            r.raise_for_status()
        except httpx2.HTTPError:
            # Listings still render (without photos) if signing is briefly unavailable.
            log.warning("storage signing failed for %d objects", len(paths), exc_info=True)
            return {}
        urls: dict[str, str] = {}
        for item in r.json():
            signed = item.get("signedURL")
            if item.get("error") or not signed:
                continue
            # The API returns a path relative to /storage/v1.
            urls[item["path"]] = f"{self._public_base}/storage/v1{signed}"
        return urls


class InMemoryStorage:
    """Test double, and a stand-in for local development without Supabase."""

    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}

    def upload(self, path: str, data: bytes, content_type: str) -> None:
        if path in self.objects:
            raise StorageError("Object exists")
        self.objects[path] = (data, content_type)

    def delete(self, paths: list[str]) -> None:
        for p in paths:
            self.objects.pop(p, None)

    def signed_urls(self, paths: list[str]) -> dict[str, str]:
        return {p: f"https://storage.test/{p}?token=signed" for p in paths if p in self.objects}

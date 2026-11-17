"""Shared photo handling for the listings and AI routes."""

import logging
import uuid

from fastapi import HTTPException, UploadFile, status

from app.core.config import Settings
from app.models import Listing, ListingImage
from app.services.images import ImageError, ProcessedImage, process_image
from app.services.storage import PhotoStorage, StorageError

log = logging.getLogger(__name__)


def _error(code: int, key: str, message: str) -> HTTPException:
    return HTTPException(code, detail={"code": key, "message": message})


def read_photos(
    files: list[UploadFile], settings: Settings, *, max_count: int
) -> list[ProcessedImage]:
    """Validate, re-encode and strip metadata from uploaded photos."""
    files = [f for f in files if f.filename or f.size]
    if not files:
        raise _error(status.HTTP_422_UNPROCESSABLE_CONTENT, "no_photos", "Add at least one photo")
    if len(files) > max_count:
        raise _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "too_many_photos",
            f"A listing can have up to {settings.max_photos_per_listing} photos",
        )
    limit = settings.max_upload_mb * 1024 * 1024
    processed: list[ProcessedImage] = []
    for f in files:
        raw = f.file.read(limit + 1)
        if len(raw) > limit:
            raise _error(
                status.HTTP_413_CONTENT_TOO_LARGE,
                "photo_too_large",
                f"Each photo must be under {settings.max_upload_mb} MB",
            )
        try:
            processed.append(process_image(raw, max_dimension=settings.image_max_dimension))
        except ImageError as exc:
            raise _error(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "bad_photo", str(exc)) from exc
    return processed


def store_photos(
    storage: PhotoStorage, listing: Listing, photos: list[ProcessedImage], *, start: int = 0
) -> list[ListingImage]:
    """Upload photos and return (unsaved) ListingImage rows. All-or-nothing."""
    uploaded: list[str] = []
    rows: list[ListingImage] = []
    try:
        for i, photo in enumerate(photos):
            image_id = uuid.uuid4()
            path = f"{listing.owner_id}/{listing.id}/{image_id}.jpg"
            storage.upload(path, photo.data, photo.content_type)
            uploaded.append(path)
            rows.append(
                ListingImage(
                    id=image_id,
                    listing_id=listing.id,
                    storage_path=path,
                    content_type=photo.content_type,
                    width=photo.width,
                    height=photo.height,
                    size_bytes=photo.size_bytes,
                    position=start + i,
                )
            )
    except StorageError as exc:
        storage.delete(uploaded)
        raise _error(
            status.HTTP_502_BAD_GATEWAY, "storage_error", "Couldn't save your photos. Try again."
        ) from exc
    return rows

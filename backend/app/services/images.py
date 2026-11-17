"""Validate and normalise uploaded photos.

Every upload is decoded and re-encoded as a fresh JPEG. That:
- rejects anything that isn't really an image, whatever its declared content type;
- drops all metadata (EXIF, including GPS coordinates that would reveal a seller's home,
  plus XMP, IPTC and embedded thumbnails) because nothing is copied into the new file;
- applies the EXIF orientation first, so phone photos aren't sideways;
- caps the size, which bounds storage costs and what we send to Claude.
"""

import io
from dataclasses import dataclass

from PIL import Image, ImageOps, UnidentifiedImageError

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
# Refuse decompression bombs: ~50 MP is well above any phone camera.
MAX_PIXELS = 50_000_000
JPEG_QUALITY = 85


class ImageError(ValueError):
    """The upload is not an acceptable photo."""


@dataclass(frozen=True)
class ProcessedImage:
    data: bytes
    width: int
    height: int
    content_type: str = "image/jpeg"

    @property
    def size_bytes(self) -> int:
        return len(self.data)


def process_image(raw: bytes, *, max_dimension: int = 2048) -> ProcessedImage:
    if not raw:
        raise ImageError("Empty file")
    try:
        with Image.open(io.BytesIO(raw)) as probe:
            fmt = probe.format
            width, height = probe.size
        if fmt not in ALLOWED_FORMATS:
            raise ImageError("Unsupported image type. Use a JPEG, PNG or WebP photo.")
        if width * height > MAX_PIXELS:
            raise ImageError("Image is too large")

        with Image.open(io.BytesIO(raw)) as img:
            img.load()
            img = ImageOps.exif_transpose(img)
            if img.mode not in ("RGB", "L"):
                # Flatten transparency onto white rather than black.
                rgba = img.convert("RGBA")
                bg = Image.new("RGB", rgba.size, (255, 255, 255))
                bg.paste(rgba, mask=rgba.getchannel("A"))
                img = bg
            elif img.mode == "L":
                img = img.convert("RGB")
            img.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)

            out = io.BytesIO()
            # No exif=/icc_profile= arguments: the new file carries no metadata at all.
            img.save(out, format="JPEG", quality=JPEG_QUALITY, optimize=True, progressive=True)
            return ProcessedImage(data=out.getvalue(), width=img.width, height=img.height)
    except ImageError:
        raise
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError) as exc:
        raise ImageError("Could not read this image") from exc

"""Helpers that build test photos in memory."""

import io

from PIL import Image

EXIF_MAKE = 0x010F
EXIF_ORIENTATION = 0x0112
GPS_IFD = 0x8825


def make_photo(
    size: tuple[int, int] = (200, 100),
    fmt: str = "JPEG",
    *,
    mode: str = "RGB",
    orientation: int | None = None,
    with_gps: bool = False,
) -> bytes:
    img = Image.new(mode, size, (200, 30, 30, 128) if mode == "RGBA" else (200, 30, 30))
    exif = Image.Exif()
    exif[EXIF_MAKE] = "TestCam"
    if orientation:
        exif[EXIF_ORIENTATION] = orientation
    if with_gps:
        gps = exif.get_ifd(GPS_IFD)
        gps[1] = "N"
        gps[2] = (38.0, 50.0, 46.0)
        gps[3] = "W"
        gps[4] = (77.0, 18.0, 23.0)
    buf = io.BytesIO()
    kwargs = {"exif": exif} if fmt in ("JPEG", "WEBP", "PNG") else {}
    img.save(buf, format=fmt, **kwargs)
    return buf.getvalue()

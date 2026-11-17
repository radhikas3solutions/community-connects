import io

import pytest
from PIL import Image

from app.services.images import ImageError, process_image
from tests.images import make_photo


def _open(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data))


def test_input_photo_really_has_metadata() -> None:
    # Guards the tests below: the fixture must contain EXIF for "stripped" to mean anything.
    assert _open(make_photo(with_gps=True)).getexif()


def test_all_metadata_is_stripped() -> None:
    out = process_image(make_photo(with_gps=True, orientation=1))
    img = _open(out.data)
    assert img.format == "JPEG"
    assert len(img.getexif()) == 0
    assert "exif" not in img.info
    assert out.content_type == "image/jpeg"
    assert out.size_bytes == len(out.data)


def test_orientation_is_applied_before_stripping() -> None:
    # EXIF orientation 6 = rotate 90° clockwise: a landscape sensor image shown as portrait.
    out = process_image(make_photo((200, 100), orientation=6))
    assert (out.width, out.height) == (100, 200)


def test_large_photos_are_downsized() -> None:
    out = process_image(make_photo((4000, 3000)), max_dimension=1000)
    assert (out.width, out.height) == (1000, 750)


@pytest.mark.parametrize("fmt", ["PNG", "WEBP"])
def test_png_and_webp_are_converted_to_jpeg(fmt: str) -> None:
    out = process_image(make_photo(fmt=fmt))
    assert _open(out.data).format == "JPEG"


def test_transparency_flattened_onto_white() -> None:
    out = process_image(make_photo(fmt="PNG", mode="RGBA"))
    assert _open(out.data).mode == "RGB"


@pytest.mark.parametrize(
    "raw",
    [b"", b"not an image at all", b"<svg xmlns='http://www.w3.org/2000/svg'></svg>"],
)
def test_non_images_rejected(raw: bytes) -> None:
    with pytest.raises(ImageError):
        process_image(raw)


def test_unsupported_format_rejected() -> None:
    with pytest.raises(ImageError, match="Unsupported"):
        process_image(make_photo(fmt="GIF"))


def test_truncated_jpeg_rejected() -> None:
    with pytest.raises(ImageError):
        process_image(make_photo()[:200])

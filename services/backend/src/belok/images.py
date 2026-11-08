from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_PIXELS = 40_000_000
MEDIA_TYPES = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}


class BadImage(ValueError):
    pass


class ImageTooLarge(BadImage):
    pass


def _open(data: bytes) -> Image.Image:
    try:
        img = Image.open(BytesIO(data), formats=list(MEDIA_TYPES))
    except (UnidentifiedImageError, OSError) as exc:
        raise BadImage("not an image") from exc
    width, height = img.size
    if width * height > MAX_PIXELS:
        img.close()
        raise ImageTooLarge(f"{width}x{height}")
    return img


def media_type(data: bytes) -> str:
    """The real type from the file header, without decoding pixels."""
    with _open(data) as img:
        return MEDIA_TYPES[img.format]


def decode(data: bytes, max_side: int, mode: str = "RGB") -> Image.Image:
    """Decode at most about max_side pixels per side, rejecting decompression bombs."""
    with _open(data) as src:
        src.draft(mode, (max_side, max_side))
        try:
            img = ImageOps.exif_transpose(src).convert(mode)
        except (OSError, Image.DecompressionBombError) as exc:
            raise BadImage("broken image") from exc
    img.thumbnail((max_side, max_side))
    return img

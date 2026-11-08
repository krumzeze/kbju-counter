import io

import pytest
from PIL import Image

from belok import images


def encode(img: Image.Image, fmt: str) -> bytes:
    out = io.BytesIO()
    img.save(out, fmt)
    return out.getvalue()


def test_media_type_comes_from_content():
    assert images.media_type(encode(Image.new("RGB", (10, 10)), "PNG")) == "image/png"
    assert images.media_type(encode(Image.new("RGB", (10, 10)), "JPEG")) == "image/jpeg"


@pytest.mark.parametrize(
    "data",
    [
        b"#!/bin/sh\nrm -rf /\n",
        b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>",
        b"GIF89a" + b"\0" * 20,
        b"",
    ],
)
def test_non_images_are_rejected(data):
    with pytest.raises(images.BadImage):
        images.media_type(data)


def test_decompression_bomb_is_rejected_before_decoding():
    bomb = encode(Image.new("1", (8000, 8000)), "PNG")
    assert len(bomb) < 1_000_000
    with pytest.raises(images.ImageTooLarge):
        images.media_type(bomb)
    with pytest.raises(images.ImageTooLarge):
        images.decode(bomb, 800)


def test_decode_downscales_and_honors_exif_rotation():
    exif = Image.Exif()
    exif[0x0112] = 6
    out = io.BytesIO()
    Image.new("RGB", (3000, 1000)).save(out, "JPEG", exif=exif)
    img = images.decode(out.getvalue(), 800)
    assert img.size == (267, 800)


def test_truncated_image_is_bad():
    data = encode(Image.new("RGB", (500, 500), (10, 200, 30)), "JPEG")
    with pytest.raises(images.BadImage):
        images.decode(data[:200], 800)

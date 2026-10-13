"""Smaller copies of rabbit photos for lists and cards, made on first request
and kept next to the original. Served through the same owner check."""

from io import BytesIO
from pathlib import PurePosixPath

from django.core.files.base import ContentFile
from PIL import Image, ImageOps

WIDTHS = (320, 640, 1280)


def rendition_name(name, width):
    path = PurePosixPath(name)
    return str(path.with_name(f"{path.stem}.w{width}.webp"))


def rendition(image_field, width):
    """The storage name of the width-limited WebP copy, making it if needed.
    Returns None when the width isn't offered or the original can't be read."""
    if width not in WIDTHS:
        return None
    storage, name = image_field.storage, image_field.name
    target = rendition_name(name, width)
    if storage.exists(target):
        return target
    try:
        with storage.open(name, "rb") as handle:
            img = ImageOps.exif_transpose(Image.open(handle))
            img.load()
    except (OSError, ValueError):
        return None
    if img.width > width:
        img = img.resize((width, round(img.height * width / img.width)), Image.LANCZOS)
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")
    out = BytesIO()
    img.save(out, "WEBP", quality=78, method=4)
    return storage.save(target, ContentFile(out.getvalue()))


def delete_renditions(storage, name):
    for width in WIDTHS:
        target = rendition_name(name, width)
        if storage.exists(target):
            storage.delete(target)

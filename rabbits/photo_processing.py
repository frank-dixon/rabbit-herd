"""Checking and cleaning uploaded rabbit photos.

Every upload is opened with Pillow and saved again as a new file. That:
- proves the file really is a JPEG, PNG or WebP image, whatever its name
  or the browser's claimed type says;
- drops all metadata (EXIF, including GPS location, camera details, XMP,
  comments), because only the pixels are written back;
- turns the picture upright first, since the EXIF orientation it relied on
  is removed;
- shrinks very large pictures to at most 2560 pixels on the long side.

HEIC isn't accepted: Pillow can't read it without an extra package. Phones
convert HEIC to JPEG on upload when the file picker asks for JPEG, PNG or
WebP, which the upload form does.
"""

from io import BytesIO

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_SOURCE_PIXELS = 50_000_000
MAX_EDGE = 2560
ACCEPT = "image/jpeg,image/png,image/webp"
FORMATS = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}

WRONG_TYPE = "A photo needs to be a JPEG, PNG or WebP image. Please choose a different file."
TOO_BIG = "A photo can be up to 10 MB. Please choose a smaller file."
UNREADABLE = "That file couldn't be opened as a photo. Please choose a different one."
TOO_MANY_PIXELS = "That photo is too large to process. Please choose a smaller one."


def clean_photo(upload):
    """Check an uploaded file and return a ContentFile with a fresh,
    metadata-free copy of the picture. Raises ValidationError with a
    message in the approved voice."""
    if upload.size > MAX_UPLOAD_BYTES:
        raise ValidationError(TOO_BIG)
    try:
        upload.seek(0)
        with Image.open(upload) as probe:
            fmt = probe.format
            width, height = probe.size
            if fmt not in FORMATS:
                raise ValidationError(WRONG_TYPE)
            if width * height > MAX_SOURCE_PIXELS:
                raise ValidationError(TOO_MANY_PIXELS)
            probe.verify()
        upload.seek(0)
        with Image.open(upload) as source:
            source.load()
            picture = ImageOps.exif_transpose(source)
    except ValidationError:
        raise
    except Image.DecompressionBombError:
        raise ValidationError(TOO_MANY_PIXELS)
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError):
        raise ValidationError(UNREADABLE)

    picture.thumbnail((MAX_EDGE, MAX_EDGE))
    output = BytesIO()
    if fmt == "JPEG":
        if picture.mode not in ("RGB", "L"):
            picture = picture.convert("RGB")
        picture.save(output, format="JPEG", quality=88, optimize=True)
    elif fmt == "PNG":
        if picture.mode not in ("RGB", "RGBA", "L", "LA", "P"):
            picture = picture.convert("RGBA")
        picture.save(output, format="PNG", optimize=True)
    else:
        if picture.mode not in ("RGB", "RGBA"):
            picture = picture.convert("RGBA" if "A" in picture.getbands() else "RGB")
        picture.save(output, format="WEBP", quality=88)
    return ContentFile(output.getvalue(), name=f"photo.{FORMATS[fmt]}")

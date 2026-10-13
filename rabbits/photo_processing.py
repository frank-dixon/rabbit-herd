"""Checking and cleaning uploaded rabbit photos.

Every upload is opened with Pillow and saved again as a new file. That:
- proves the file really is a JPEG, PNG, WebP or HEIC image, whatever its name
  or the browser's claimed type says;
- drops all metadata (EXIF, including GPS location, camera details, XMP,
  comments), because only the pixels are written back;
- turns the picture upright first, since the EXIF orientation it relied on
  is removed;
- shrinks very large pictures to at most 2560 pixels on the long side.

HEIC and HEIF (what iPhones and Macs save, sometimes under a .jpeg name)
are read with pillow-heif and stored as JPEG, since browsers can't all
show HEIC.
"""

import datetime
from io import BytesIO

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError
from pillow_heif import register_heif_opener

register_heif_opener()

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_SOURCE_PIXELS = 50_000_000
MAX_EDGE = 2560
ACCEPT = "image/jpeg,image/png,image/webp,image/heic,image/heif,.heic,.heif"
FORMATS = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}
# Formats that are stored as one of FORMATS. MPO is the multi-picture JPEG
# that iPhones save for portrait and some other photos; Pillow names it MPO
# even though the file is a JPEG. Only its first picture is kept. HEIF
# (which Pillow also uses for HEIC) is converted to JPEG.
SAVE_AS = {"MPO": "JPEG", "HEIF": "JPEG"}

WRONG_TYPE = "A photo needs to be a JPEG, PNG, WebP or HEIC image. Choose a different file."
TOO_BIG = "A photo can be up to 10 MB. Choose a smaller file."
UNREADABLE = "That file couldn't be opened as a photo. Choose a different one."
TOO_MANY_PIXELS = "That photo is too large to process. Choose a smaller one."


EXIF_IFD = 0x8769
DATE_TAGS = (36867, 36868)  # DateTimeOriginal, DateTimeDigitized
IFD0_DATETIME = 306


def parse_exif_date(text):
    """ "2026:03:03 14:22:01" (EXIF) or "2026-03-03" to a date, else None."""
    text = str(text or "").strip().replace("\x00", "")
    if len(text) < 10:
        return None
    try:
        return datetime.date(int(text[0:4]), int(text[5:7]), int(text[8:10]))
    except ValueError:
        return None


def read_taken_date(upload):
    """The date a photo was taken, from DateTimeOriginal, then DateTimeDigitized,
    then the main DateTime, read before anything is stripped. JPEG, HEIC
    (through pillow-heif) and WebP all expose it the same way. None if absent."""
    try:
        upload.seek(0)
        with Image.open(upload) as probe:
            exif = probe.getexif()
            inner = exif.get_ifd(EXIF_IFD) if exif else {}
            for tag in DATE_TAGS:
                found = parse_exif_date(inner.get(tag))
                if found:
                    return found
            return parse_exif_date(exif.get(IFD0_DATETIME)) if exif else None
    except Exception:
        return None
    finally:
        try:
            upload.seek(0)
        except Exception:
            pass


def clean_photo(upload):
    """Check an uploaded file and return a ContentFile with a fresh,
    metadata-free copy of the picture. Raises ValidationError with a
    message in the approved voice."""
    if upload.size > MAX_UPLOAD_BYTES:
        raise ValidationError(TOO_BIG)
    try:
        upload.seek(0)
        with Image.open(upload) as probe:
            fmt = SAVE_AS.get(probe.format, probe.format)
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


def rotate_photo(field_file, direction):
    """A quarter-turn copy of a stored photo as a ContentFile, in the same format."""
    with field_file.open("rb") as handle:
        with Image.open(handle) as source:
            source.load()
            fmt = SAVE_AS.get(source.format, source.format)
            if fmt not in FORMATS:
                fmt = "JPEG"
            turned = source.transpose(Image.Transpose.ROTATE_90 if direction == "left" else Image.Transpose.ROTATE_270)
    output = BytesIO()
    if fmt == "JPEG":
        if turned.mode not in ("RGB", "L"):
            turned = turned.convert("RGB")
        turned.save(output, format="JPEG", quality=88, optimize=True)
    else:
        turned.save(output, format=fmt)
    return ContentFile(output.getvalue(), name=f"photo.{FORMATS[fmt]}")

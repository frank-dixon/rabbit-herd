"""Photos on the add-a-rabbit flow.

Uploads go through the same pipeline as the Photos page (photo_processing: type
check, EXIF date, rotation, shrink, metadata stripped) and wait in storage under
flow-pending/<user id>/ until the rabbit is saved. The draft keeps them in the
order they were picked; the first is the main photo. Saving the rabbit turns them
into RabbitPhoto rows; starting over or saving removes the pending files.
"""

import uuid

from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage

from . import photo_processing

PENDING_DIR = "flow-pending"
MAX_PHOTOS = 12
TOO_MANY = f"A new rabbit can start with up to {MAX_PHOTOS} photos. Add more from its Photos page later."


def blank_photo():
    return {"name": "", "taken": "", "label": ""}


def clean_photos(rows):
    """Session rows, keeping only pending files under PENDING_DIR."""
    cleaned = []
    if isinstance(rows, list):
        for row in rows[:MAX_PHOTOS]:
            if not isinstance(row, dict):
                continue
            name = str(row.get("name") or "")
            if not name.startswith(f"{PENDING_DIR}/") or ".." in name:
                continue
            cleaned.append({"name": name, "taken": str(row.get("taken") or "")[:10], "label": str(row.get("label") or "")[:120]})
    return cleaned


def add_uploads(draft, user, files, hint=""):
    """Process each upload in the order given and append it. Returns error texts."""
    errors = []
    for upload in files:
        if len(draft["photos"]) >= MAX_PHOTOS:
            errors.append(TOO_MANY)
            break
        try:
            taken = photo_processing.read_taken_date(upload) or photo_processing.parse_exif_date(hint)
            content = photo_processing.clean_photo(upload)
        except ValidationError as error:
            errors.append(f"{upload.name}: {error.messages[0]}")
            continue
        ext = content.name.rsplit(".", 1)[-1]
        name = default_storage.save(f"{PENDING_DIR}/{user.pk}/{uuid.uuid4().hex}.{ext}", content)
        draft["photos"].append({"name": name, "taken": taken.isoformat()[:10] if taken else "", "label": upload.name[:120]})
    return errors


def apply_action(draft, action):
    """photo-remove-N, photo-main-N, photo-up-N, photo-down-N. True when handled."""
    for verb in ("remove", "main", "up", "down"):
        prefix = f"photo-{verb}-"
        if action.startswith(prefix) and action[len(prefix):].isdigit():
            break
    else:
        return False
    photos = draft["photos"]
    index = int(action[len(prefix):])
    if index >= len(photos):
        return True
    if verb == "remove":
        delete_file(photos.pop(index)["name"])
    elif verb == "main":
        photos.insert(0, photos.pop(index))
    elif verb == "up" and index > 0:
        photos[index - 1], photos[index] = photos[index], photos[index - 1]
    elif verb == "down" and index < len(photos) - 1:
        photos[index + 1], photos[index] = photos[index], photos[index + 1]
    return True


def reorder(draft, order):
    """Apply a new order from the page (a list of current indexes)."""
    photos = draft["photos"]
    if sorted(order) != list(range(len(photos))):
        return False
    draft["photos"] = [photos[i] for i in order]
    return True


def delete_file(name):
    try:
        default_storage.delete(name)
    except OSError:
        pass


def discard(draft):
    for row in draft.get("photos", []):
        delete_file(row["name"])
    draft["photos"] = []


def attach(rabbit, draft):
    """Turn the pending files into the rabbit's photos; the first is the main one."""
    import datetime

    from django.core.files.base import ContentFile

    from .models import RabbitPhoto, valid_taken_date

    for index, row in enumerate(draft.get("photos", [])):
        try:
            with default_storage.open(row["name"], "rb") as handle:
                data = handle.read()
        except (FileNotFoundError, OSError):
            continue
        taken = None
        if row["taken"]:
            try:
                taken = valid_taken_date(datetime.date.fromisoformat(row["taken"]), rabbit.birth_date)
            except ValueError:
                taken = None
        photo = RabbitPhoto(rabbit=rabbit, is_main=index == 0 and not rabbit.photos.filter(is_main=True).exists(),
                            taken_at=taken, taken_from_metadata=taken is not None)
        photo.image.save("photo." + row["name"].rsplit(".", 1)[-1], ContentFile(data), save=False)
        photo.save()
        delete_file(row["name"])
    draft["photos"] = []

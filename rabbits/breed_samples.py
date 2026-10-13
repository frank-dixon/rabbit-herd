"""Breed sample photos for the add-a-rabbit photos card.

Only openly licensed pictures (CC0, public domain or CC BY) from Wikimedia
Commons, listed in breed_photos.json with file, source, license and author, so
the credit can be shown. A sample is only ever shown on the card until a real
photo is added; it is never saved as the rabbit's photo or used anywhere else.
Breeds without one get a plain silhouette.
"""

import json
import re
from functools import lru_cache
from pathlib import Path

MANIFEST = Path(__file__).with_name("breed_photos.json")
ALLOWED_LICENSE = re.compile(r"^(CC0( 1\.0)?|Public domain|CC BY \d\.\d)$", re.I)
SILHOUETTE = "img/breeds/silhouette.svg"


@lru_cache(maxsize=1)
def manifest():
    if not MANIFEST.exists():
        return {}
    data = json.loads(MANIFEST.read_text())
    return {name: row for name, row in data.items() if ALLOWED_LICENSE.match(row.get("license", ""))}


def sample_for(breed):
    """{"file", "credit", "source", "license", "is_photo"} for the card, from a Breed (or None)."""
    row = manifest().get(breed.name) if breed is not None else None
    if not row:
        return {"file": SILHOUETTE, "is_photo": False, "breed": breed.name if breed else ""}
    credit = f"{row['author']} · {row['license']} · Wikimedia Commons"
    return {"file": row["file"], "is_photo": True, "breed": breed.name, "credit": credit,
            "source": row["source"], "license": row["license"], "license_url": row.get("license_url", "")}

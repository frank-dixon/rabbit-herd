from django import template
from django.urls import reverse
from django.utils.html import escape
from django.utils.safestring import mark_safe

from rabbits.renditions import WIDTHS

register = template.Library()


@register.simple_tag
def photo_src(photo, sizes="100vw", largest=1280):
    """src, srcset and sizes attributes for a rabbit photo, pointing at its
    WebP copies. The src fallback is the middle width offered."""
    base = escape(f"{reverse('rabbit_photo_file', args=[photo.pk])}?v={photo.image.name[-12:]}")
    widths = [w for w in WIDTHS if w <= int(largest)] or [WIDTHS[0]]
    srcset = ", ".join(f"{base}&amp;w={w} {w}w" for w in widths)
    fallback = widths[min(1, len(widths) - 1)]
    return mark_safe(f'src="{base}&amp;w={fallback}" srcset="{srcset}" sizes="{escape(sizes)}"')


@register.simple_tag
def ancestor_thumb(rabbit, color=""):
    """What one ancestor's thumbnail shows: a herd rabbit's main photo, an
    outside ancestor's own photo, or a coat-matched stock placeholder.
    Returns {"photo": RabbitPhoto or None, "src": url, "placeholder": bool}."""
    from rabbits.litter_photos import coat_placeholder_url, outside_photo_url
    from rabbits.models import Rabbit

    if isinstance(rabbit, Rabbit):
        main = rabbit.main_photo
        if main:
            return {"photo": main, "src": "", "placeholder": False}
        color = color or rabbit.color
    elif getattr(rabbit, "photo", None):
        return {"photo": None, "src": outside_photo_url(rabbit, 320), "placeholder": False}
    else:
        # Outside details read like "Black doe · Kessler New Zealands · KNZ0412".
        color = color or (getattr(rabbit, "details", "") or "").split("·")[0]
    return {"photo": None, "src": coat_placeholder_url(color), "placeholder": True}

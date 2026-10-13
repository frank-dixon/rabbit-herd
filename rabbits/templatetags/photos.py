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

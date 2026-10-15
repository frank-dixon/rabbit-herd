"""The shared delete confirm page: what a delete URL shows on GET (no JavaScript, or a link opened directly)."""
from django.shortcuts import render


def confirm_delete(request, title, text, cancel_href, label="Delete"):
    return render(request, "components/confirm_delete_page.html", {
        "title": title, "text": text, "action": request.path, "cancel_href": cancel_href, "label": label,
    })

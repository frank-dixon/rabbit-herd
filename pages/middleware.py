def prefetch_keeps_messages(get_response):
    """A link prefetched on hover may never be opened, so it must not use up
    one-time messages meant for the page the keeper actually opens next."""

    def middleware(request):
        response = get_response(request)
        if request.headers.get("Sec-Purpose", "").startswith("prefetch") and hasattr(request, "_messages"):
            request._messages.used = False
        return response

    return middleware

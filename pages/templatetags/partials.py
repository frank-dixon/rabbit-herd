from django import template

register = template.Library()

CONTROL_CLASS = "mt-1 w-full rounded border bg-white px-3 py-2"


@register.filter
def styled_widget(field):
    """Render a BoundField with the shared control classes.

    Date inputs get type="date" when the widget has not set a type.
    """
    widget = field.field.widget
    attrs = widget.attrs.copy()
    if getattr(widget, "input_type", None) == "checkbox":
        attrs["class"] = "h-4 w-4"
    else:
        border = "border-neutral-800" if field.errors else "border-neutral-400"
        attrs["class"] = f"{CONTROL_CLASS} {border}"
        if str(widget.template_name).endswith("/date.html"):
            attrs.setdefault("type", "date")
    return field.as_widget(attrs=attrs)

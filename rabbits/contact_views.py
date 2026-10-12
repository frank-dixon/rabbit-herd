"""Contacts: the people and rabbitries a keeper buys from, sells to, or
uses studs from. Everything is scoped to the signed-in owner."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .contact_forms import ContactForm
from .models import Contact, Rabbit

ROLES = {"buyer": "is_buyer", "breeder": "is_breeder", "stud-owner": "is_stud_owner"}


def owned_contact(user, pk):
    return get_object_or_404(Contact, owner=user, pk=pk)


@login_required
def contact_list(request):
    role = request.GET.get("role") if request.GET.get("role") in ROLES else ""
    contacts = Contact.objects.filter(owner=request.user)
    if role:
        contacts = contacts.filter(**{ROLES[role]: True})
    return render(request, "rabbits/contacts/list.html", {
        "contacts": list(contacts), "role": role, "wide": True,
        "roles": [("", "All"), ("buyer", "Buyers"), ("breeder", "Breeders"), ("stud-owner", "Stud owners")],
    })


@login_required
def contact_create(request):
    form = ContactForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        contact = form.save(commit=False)
        contact.owner = request.user
        contact.save()
        messages.success(request, f"{contact.name} was added to your contacts.")
        return redirect("contact_detail", pk=contact.pk)
    return render(request, "rabbits/contacts/form.html", {"form": form, "heading": "Add a contact", "submit_label": "Save contact"})


@login_required
def contact_edit(request, pk):
    contact = owned_contact(request.user, pk)
    form = ContactForm(request.POST or None, instance=contact)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "The contact was saved.")
        return redirect("contact_detail", pk=contact.pk)
    return render(request, "rabbits/contacts/form.html", {
        "form": form, "heading": f"Edit {contact.name}", "submit_label": "Save contact", "contact": contact,
    })


def contact_rabbits(contact):
    """Every rabbit that came from or went to this contact, with which way."""
    rows = [(rabbit, "Came from them") for rabbit in contact.rabbits_from.all().prefetch_related("photos")]
    sales = getattr(contact, "purchases", None)
    if sales is not None:
        rows += [(sale.rabbit, f"Sold to them · {sale.date:%b} {sale.date.day}, {sale.date.year}")
                 for sale in sales.select_related("rabbit").prefetch_related("rabbit__photos")]
    return rows


@login_required
def contact_detail(request, pk):
    contact = owned_contact(request.user, pk)
    context = {"contact": contact, "rabbits": contact_rabbits(contact), "wide": True}
    studs = getattr(contact, "outside_rabbits", None)
    if studs is not None:
        context["studs"] = list(studs.all())
    return render(request, "rabbits/contacts/detail.html", context)


@login_required
@require_POST
def rabbit_source(request, pk):
    """Pick (or clear) the contact a rabbit came from, from its page."""
    rabbit = get_object_or_404(Rabbit, owner=request.user, pk=pk)
    raw = request.POST.get("source", "")
    if raw == "":
        rabbit.source = None
    elif raw.isdigit() and Contact.objects.filter(owner=request.user, pk=int(raw)).exists():
        rabbit.source_id = int(raw)
    else:
        messages.error(request, "Please choose one of your contacts.")
        return redirect("rabbit_detail", pk=rabbit.pk)
    rabbit.save(update_fields=["source", "updated_at"])
    messages.success(request, "Where it came from was saved.")
    return redirect("rabbit_detail", pk=rabbit.pk)

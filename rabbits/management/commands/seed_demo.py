"""Seed (or refresh) the demo account: demo@bramble-burrow.app with a lived-in herd.

The password is read from the DEMO_PASSWORD environment variable inside the command;
it is never taken as an argument, printed or logged. --no-password leaves the password
alone: an existing account keeps its password; a new one gets no usable password (set it
with `manage.py changepassword`).

Every rabbit gets a saved main photo of its breed, from rabbits/demo_photos/ (Wikimedia
Commons, CC/PD; author, license and source in attribution.json and in the photo's notes).

Idempotent: re-running updates the account and rebuilds the demo herd in place, so
nothing is duplicated. Dates are relative to today, so the herd always looks current.
Only the demo account's own data is touched.
"""
import datetime
import json
import os
from pathlib import Path
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from rabbits.models import (Breed, Contact, CullNote, Expense, HealthNote, HerdSettings, Litter, Location, Pairing,
                            Rabbit, RabbitPhoto, Task, WaitlistEntry, Weight)
from rabbits.renditions import delete_renditions

DEMO_EMAIL = "demo@bramble-burrow.app"

# name, sex, breed, color, age in days, status, extra
HERD = [
    # Breeding bucks
    ("Ashford", "buck", "Mini Rex", "Castor", 690, "breeding", {"tattoo": "HC2403", "line": "Hollow Creek"}),
    ("Merrick", "buck", "Holland Lop", "Broken Chestnut", 540, "breeding", {"tattoo": "HC2411", "line": "Fairhaven"}),
    # Does in the herd
    ("Juniper", "doe", "Mini Rex", "Black", 820, "breeding", {"tattoo": "HC2302"}),
    ("Marigold", "doe", "Mini Rex", "Broken Castor", 610, "breeding", {"tattoo": "HC2405"}),
    ("Sorrel", "doe", "Mini Rex", "Red", 480, "breeding", {"tattoo": "HC2414"}),
    ("Willa", "doe", "Mini Rex", "Opal", 400, "breeding", {"tattoo": "HC2420"}),
    ("Thimble", "doe", "Holland Lop", "Tort", 560, "breeding", {"tattoo": "HC2409"}),
    ("Pippa", "doe", "Holland Lop", "Broken Tort", 450, "breeding", {"tattoo": "HC2416"}),
    ("Clementine", "doe", "Holland Lop", "Chestnut", 365, "breeding", {"tattoo": "HC2502"}),
    ("Hazel", "doe", "Mini Rex", "Lynx", 300, "breeding", {"tattoo": "HC2507"}),
    ("Briar", "doe", "Mini Rex", "Castor", 92, "growing", {"tattoo": "HC2603", "kit_of": "weaned"}),
    ("Nettle", "doe", "Mini Rex", "Broken Castor", 92, "growing", {"tattoo": "HC2604", "kit_of": "weaned"}),
    ("Fennel", "doe", "Holland Lop", "Broken Chestnut", 130, "growing", {"tattoo": "HC2601"}),
    ("Rosalind", "doe", "Holland Lop", "Black Otter", 135, "growing", {"tattoo": "HC2602"}),
    # Former bucks
    ("Barnaby", "buck", "Mini Rex", "Blue", 1500, "deceased", {"died": 120, "cause": "Old age", "tattoo": "HC2201"}),
    ("Cobalt", "buck", "Mini Rex", "Seal", 320, "culled", {"died": 60, "cull": "Narrow shoulders and a long body; not worth using.", "tattoo": "HC2508"}),
    ("Wexley", "buck", "Holland Lop", "Fawn", 250, "culled", {"died": 30, "cull": "Crown set too far back and ears not lopped fully.", "tattoo": "HC2512"}),
    # Culled does
    ("Elsie", "doe", "Mini Rex", "Otter", 1100, "culled", {"died": 200, "cull": "Missed three breedings in a row.", "tattoo": "HC2208"}),
    ("Tansy", "doe", "Mini Rex", "Chocolate", 900, "culled", {"died": 150, "cull": "Two litters lost to poor mothering.", "tattoo": "HC2305"}),
    ("Maple", "doe", "Holland Lop", "Sable Point", 700, "culled", {"died": 110, "cull": "Malocclusion showed up in her kits.", "tattoo": "HC2310"}),
    ("Rue", "doe", "Mini Rex", "Red", 330, "culled", {"died": 80, "cull": "Coat too long and soft; poor density.", "tattoo": "HC2506"}),
    ("Delphine", "doe", "Holland Lop", "Tort", 260, "culled", {"died": 45, "cull": "Pinched hindquarters.", "tattoo": "HC2510"}),
    ("Saffron", "doe", "Mini Rex", "Broken Red", 210, "culled", {"died": 25, "cull": "Off-color undercoat for a red.", "tattoo": "HC2514"}),
    ("Lark", "doe", "Holland Lop", "Chestnut", 190, "culled", {"died": 12, "cull": "Weight well over senior limit at six months.", "tattoo": "HC2516"}),
    # Sold to other rabbitries
    ("Calder", "buck", "Mini Rex", "Castor", 280, "sold", {"buyer": 0, "tattoo": "HC2509"}),
    ("Odette", "doe", "Mini Rex", "Black", 240, "sold", {"buyer": 1, "tattoo": "HC2511"}),
    ("Fable", "doe", "Holland Lop", "Broken Tort", 200, "sold", {"buyer": 2, "tattoo": "HC2515"}),
    ("Quill", "buck", "Holland Lop", "Black Otter", 175, "sold", {"buyer": 3, "tattoo": "HC2517"}),
    ("Ivy", "doe", "Mini Rex", "Opal", 160, "sold", {"buyer": 0, "tattoo": "HC2518"}),
]

BUYERS = [
    ("Dana Whitfield", "Whitfield Farm Rabbitry", "(717) 555-0142", "Lancaster, PA"),
    ("Marcus Ortega", "Cedar Run Rex", "(540) 555-0187", "Winchester, VA"),
    ("Lena Haugen", "Northwind Lops", "(608) 555-0119", "Madison, WI"),
    ("Priya Raman", "Bluebell Hollow", "(919) 555-0163", "Raleigh, NC"),
]
BREEDERS = [
    ("Tom Kessler", "Kessler Mini Rex", "(330) 555-0124", "Wooster, OH"),
    ("Ruth Ellison", "Fairhaven Hollands", "(410) 555-0158", "Frederick, MD"),
]

# Typical adult weight (grams) by breed and sex, and a kit's growth curve.
ADULT = {("Mini Rex", "doe"): 1900, ("Mini Rex", "buck"): 1750, ("Holland Lop", "doe"): 1700, ("Holland Lop", "buck"): 1600}


def sold_days(extra):
    """Days ago a sold rabbit left (spread out by buyer)."""
    return extra["buyer"] * 10 + 5 + (len(extra.get("tattoo", "")) % 3)


def growth(age_days, adult):
    """Rough weight for a young rabbit, reaching adult weight around 8 months."""
    if age_days >= 240:
        return adult
    return int(90 + (adult - 90) * min(1, age_days / 240) ** 0.8)


class Command(BaseCommand):
    help = "Create or refresh the demo account (demo@bramble-burrow.app) and its herd. Password from env DEMO_PASSWORD."

    def add_arguments(self, parser):
        parser.add_argument("--no-password", action="store_true",
                            help="Don't set the password: an existing account keeps its own; a new one gets none.")

    def handle(self, no_password=False, **options):
        password = None if no_password else os.environ.get("DEMO_PASSWORD")
        if not no_password and not password:
            raise CommandError("Set DEMO_PASSWORD in the environment, or pass --no-password.")
        with transaction.atomic():
            user, created = self.account(password)
            counts = self.herd(user, timezone.localdate())
        self.stdout.write(("Created" if created else "Updated") + f" {DEMO_EMAIL}.")
        self.stdout.write(", ".join(f"{k}: {v}" for k, v in counts.items()))

    def account(self, password):
        User = get_user_model()
        user = User.objects.filter(email__iexact=DEMO_EMAIL).first()
        created = user is None
        if created:
            user = User.objects.create_user(email=DEMO_EMAIL)
        if password:
            user.set_password(password)
        elif created:
            user.set_unusable_password()  # --no-password on a new account; an existing one keeps its password
        user.email_confirmed = True
        user.email_confirmed_at = user.email_confirmed_at or timezone.now()
        user.is_active = True
        user.save()
        HerdSettings.objects.update_or_create(user=user, defaults={"rabbitry_name": "Hollow Creek Rabbitry", "prefix": "HC"})
        return user, created

    def herd(self, user, today):
        day = lambda n: today - datetime.timedelta(days=n)  # noqa: E731
        # Rebuild only the demo account's herd, so re-runs update rather than duplicate.
        old_files = list(RabbitPhoto.objects.filter(rabbit__owner=user).values_list("image", flat=True))
        for model in (Task, WaitlistEntry, Expense, Litter, Pairing, Rabbit, Contact, Location):
            model.objects.filter(owner=user).delete()

        breeds = {b.name: b for b in Breed.objects.filter(name__in={row[2] for row in HERD})}
        buyers = [Contact.objects.create(owner=user, name=n, rabbitry=r, phone=p, location=loc, is_buyer=True,
                                         notes="Bought show stock.") for n, r, p, loc in BUYERS]
        breeders = [Contact.objects.create(owner=user, name=n, rabbitry=r, phone=p, location=loc, is_breeder=True)
                    for n, r, p, loc in BREEDERS]

        rabbits = {}
        for name, sex, breed, color, age, status, extra in HERD:
            death = day(extra["died"]) if "died" in extra else None
            source = None if extra.get("kit_of") else (breeders[0] if breed == "Mini Rex" else breeders[1]) if age > 500 else None
            rabbits[name] = Rabbit.objects.create(
                owner=user, name=name, sex=sex, breed=breed, breed_type="purebred", purebred=breeds.get(breed),
                color=color, birth_date=day(age), status=status, tattoo=extra.get("tattoo", ""),
                line=extra.get("line", ""), death_date=death if status in ("culled", "deceased") else None,
                death_cause=extra.get("cause", "Culled" if status == "culled" else ""), source=source)

        R = rabbits
        photos = self.photos(R, old_files)
        # Litters: weaned (Briar and Nettle came from it), nursing, due soon, just bred.
        def litter(doe, buck, bred, **kw):
            pairing = Pairing.objects.get_or_create(owner=user, doe=R[doe], buck=R[buck])[0]
            return Litter.objects.create(owner=user, pairing=pairing, bred_on=day(bred), palpated=bred >= 12, **kw)

        weaned = litter("Juniper", "Ashford", 123, nest_box_in=True, kindled_on=day(92), born_alive=7, died_after=1,
                        weaned=True, notes="Two castors and a broken held back.")
        for kit in ("Briar", "Nettle"):
            R[kit].litter = weaned
            R[kit].save(update_fields=["litter"])
        litter("Thimble", "Merrick", 52, nest_box_in=True, kindled_on=day(21), born_alive=5, born_dead=1,
               notes="Good nest, all kits fat.")
        litter("Marigold", "Ashford", 27, nest_box_in=False)
        litter("Pippa", "Merrick", 9)
        litter("Sorrel", "Ashford", 200, nest_box_in=True, kindled_on=day(169), born_alive=6, weaned=True, processed=True)

        # Weights: every two weeks for the last four months, ending today for most.
        weights = 0
        for name, sex, breed, color, age, status, extra in HERD:
            adult = ADULT[(breed, sex)]
            last = extra.get("died", 0) if status in ("culled", "deceased") else 0
            if status == "sold":
                last = sold_days(extra)
            for back in range(last, last + 120, 14):
                a = age - back
                if a < 35:
                    break
                grams = growth(a, adult) + ((sum(map(ord, name)) + back) % 7 - 3) * 15
                Weight.objects.create(rabbit=R[name], date=day(back), grams=grams)
                weights += 1

        # Sales: buyer contacts and the waitlist entries they came from.
        for name, *_, status, extra in HERD:
            if status != "sold":
                continue
            rabbit, buyer = R[name], buyers[extra["buyer"]]
            sold_on = day(sold_days(extra))
            WaitlistEntry.objects.create(owner=user, buyer=f"{buyer.name} ({buyer.rabbitry})", reach=buyer.phone,
                                         requested_on=sold_on - datetime.timedelta(days=40), breed=rabbit.breed,
                                         sex=rabbit.sex, color=rabbit.color, status="done", deposit=Decimal("25.00"),
                                         rabbit=rabbit, notes=f"Sold {sold_on:%b} {sold_on.day}; picked up at the farm.")
        WaitlistEntry.objects.create(owner=user, buyer="Kate Brennan", reach="(814) 555-0176", requested_on=day(18),
                                     breed="Mini Rex", sex="doe", color="Broken Castor", notes="Wants show quality.")
        WaitlistEntry.objects.create(owner=user, buyer="Samuel Okafor (Riverbend Rabbitry)", reach="(502) 555-0131",
                                     requested_on=day(6), breed="Holland Lop", sex="buck", status="offered",
                                     deposit=Decimal("30.00"))

        # Keep-or-cull notes for the culls and two growers still under evaluation.
        culls = 0
        for name, *_, extra in HERD:
            if "cull" in extra:
                CullNote.objects.create(rabbit=R[name], date=day(extra["died"] + 3), decision="cull", reason=extra["cull"])
                culls += 1
        CullNote.objects.create(rabbit=R["Briar"], date=day(6), decision="keep", reason="Dense coat, good depth.")
        CullNote.objects.create(rabbit=R["Nettle"], date=day(6), decision="undecided", reason="Recheck shoulders at 4 months.")

        health = [
            ("Juniper", 40, "checkup", "Nails trimmed, teeth fine, good condition.", None),
            ("Thimble", 21, "checkup", "Post-kindling check; eating well.", None),
            ("Merrick", 15, "treatment", "Ivermectin for ear mites, second dose due.", 1),
            ("Willa", 9, "illness", "Mild weepy eye; flushing with saline.", -3),
            ("Ashford", 70, "injury", "Small nick on the hock from the cage floor; added a resting mat.", None),
            ("Fennel", 30, "checkup", "Molting; on track for weight.", None),
            ("Barnaby", 140, "illness", "Slowing down, softer appetite.", None),
        ]
        for name, back, kind, notes, follow in health:
            HealthNote.objects.create(rabbit=R[name], date=day(back), kind=kind, notes=notes,
                                      follow_up_on=day(-follow) if follow is not None else None)

        tasks = [
            ("Clean and disinfect the nest boxes", -2, None, "weekly"),
            ("Order 50 lb pellets", -4, None, ""),
            ("Tattoo the Juniper litter keepers", 3, None, ""),
            ("Recheck Willa's eye", -3, "Willa", ""),
            ("Trim nails", 5, None, "monthly"),
            ("Enter the Keystone show", 12, None, ""),
            ("Replace water bottle in the grow-out pen", 1, None, ""),
        ]
        for title, ahead, rabbit, repeat in tasks:
            Task.objects.create(owner=user, title=title, due_on=day(-ahead), rabbit=R.get(rabbit), repeat=repeat)

        expenses = [(3, "feed", "50 lb rabbit pellets", "24.99", "50"), (17, "hay", "Timothy hay, 2 bales", "28.00", None),
                    (25, "supplies", "Water bottles (6)", "18.50", None), (40, "vet", "Ivermectin", "15.75", None),
                    (60, "shows", "Keystone Classic entries", "24.00", None), (33, "feed", "50 lb rabbit pellets", "24.99", "50")]
        for back, cat, desc, amount, lb in expenses:
            Expense.objects.create(owner=user, date=day(back), category=cat, description=desc, amount=Decimal(amount),
                                   weight_lb=Decimal(lb) if lb else None)

        alive = Rabbit.objects.filter(owner=user).exclude(status__in=Rabbit.FORMER)
        return {
            "bucks alive": alive.filter(sex="buck").count(), "does alive": alive.filter(sex="doe").count(),
            "bucks culled/deceased": Rabbit.objects.filter(owner=user, sex="buck", status__in=("culled", "deceased")).count(),
            "does culled": Rabbit.objects.filter(owner=user, sex="doe", status="culled").count(),
            "sold": Rabbit.objects.filter(owner=user, status="sold").count(),
            "contacts": Contact.objects.filter(owner=user).count(), "litters": Litter.objects.filter(owner=user).count(),
            "weights": weights, "health": len(health), "tasks": Task.objects.filter(owner=user).count(),
            "cull notes": culls + 2, "photos": photos, "waitlist": WaitlistEntry.objects.filter(owner=user).count(),
        }

    def photos(self, rabbits, old_files):
        """Main photo per rabbit, cycling through its breed's licensed photos (color matches first)."""
        from django.core.files.storage import default_storage
        from django.db import transaction as tx

        for name in old_files:  # the previous run's files, removed once this run commits
            tx.on_commit(lambda n=name: (default_storage.delete(n), delete_renditions(default_storage, n)))
        folder = Path(__file__).resolve().parents[2] / "demo_photos"
        credits = json.loads((folder / "attribution.json").read_text())
        by_breed, used = {}, {}
        for c in credits:
            by_breed.setdefault(c["breed"], []).append(c)
        count = 0
        for rabbit in rabbits.values():
            pool = by_breed.get(rabbit.breed)
            if not pool:
                continue
            words = set(rabbit.color.lower().split())
            fresh = [c for c in pool if used.get(c["file"], 0) == min(used.get(p["file"], 0) for p in pool)]
            pick = next((c for c in fresh if words & set(c["file"].replace("-", " ").split())), fresh[0])
            used[pick["file"]] = used.get(pick["file"], 0) + 1
            photo = RabbitPhoto(rabbit=rabbit, is_main=True,
                                notes=f"Demo photo: {pick['author']}, {pick['license']}, via Wikimedia Commons ({pick['source']}).")
            with open(folder / pick["file"], "rb") as handle:
                photo.image.save("photo.jpg", File(handle), save=False)
            photo.save()
            count += 1
        return count

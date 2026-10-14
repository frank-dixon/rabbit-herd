"""Seed (or refresh) the demo account: a New Zealand rabbitry with Californian
crosses, broken colors, and every major feature exercised.

Login: demo@bramble-burrow.app. Password from DEMO_PASSWORD only (never printed).
--no-password leaves an existing password alone. --genes-only rewrites genes on
the existing demo rabbits by name without touching anything else.

Idempotent: rebuilds only the demo account's own data. Dates are relative to
today so the herd always looks current. Never touches other users.
"""
import datetime
import json
import os
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from rabbits.models import (
    Breed, BreedingSchedule, Contact, Cover, CullNote, Expense, Gene, HealthNote,
    HerdSettings, KitCheck, Litter, LitterCheck, LitterKit, Location, OutsideRabbit,
    Pairing, PedigreeEntry, Program, ProgramBreeder, Rabbit, RabbitPhoto, Relative,
    ShowEntry, Task, WaitlistEntry, Weight,
)
from rabbits.models import PEDIGREE_POSITIONS, LitterNote

DEMO_EMAIL = "demo@bramble-burrow.app"
NZ = "New Zealand"
CAL = "Californian"
GENE_LOCI = ["A", "B", "C", "D", "E", "En"]

# Kit growth (grams) at weeks 1..10. Pure NZ from the New Zealand White (NN)
# means in Abdel-Hamid 2015 (J. Adv. Vet. Anim. Res. 2:120–127, Egypt
# 3×3 diallel; Table of body weight at 4/6/8/10 wk: 590 / 1105 / 1494 / 1810).
# Weeks 1–3, 5, 7, 9 are linear interpolations between those and a ~60 g birth
# weight. NZ×Californian (NN×CC in the same table: 607 / 1307 / 1710 / 1977)
# shows the hybrid vigor reported there (and by Maj et al. 2009, Arch. Anim.
# Breed. 52:205–210). Adult NZ meat rabbits settle near 4.5–5.5 kg.
NZ_CURVE = {1: 150, 2: 290, 3: 430, 4: 590, 5: 850, 6: 1105, 7: 1300, 8: 1494, 9: 1650, 10: 1810}
XC_CURVE = {1: 160, 2: 310, 3: 460, 4: 607, 5: 960, 6: 1307, 7: 1510, 8: 1710, 9: 1840, 10: 1977}
ADULT = {
    (NZ, "doe"): 4800, (NZ, "buck"): 5000,
    (CAL, "doe"): 4300, (CAL, "buck"): 4500,
}

# name, sex, breed, color, age_days, status, genes "A B C D E En", extras.
# NZ red is A_ ee (agouti-based red with rufus); reds carry a where the pedigree allows.
# Genes follow each rabbit's recorded parents; carriers are deliberate.
# "dam"/"sire" name herd rabbits; "dam_out"/"sire_out" name outside ancestors.
HERD = [
    # Founders and old stock (bought in ~4 years ago)
    ("Basalt", "buck", NZ, "Black", 1600, "deceased", "aa BB Cc Dd EE enen",
     {"tattoo": "NZ2201", "died": 200, "cause": "Old age", "dam_out": "Nightshade", "sire_out": "Old Coal"}),
    ("Nimbus", "doe", NZ, "Blue", 1450, "deceased", "aa BB Cc dd EE enen",
     {"tattoo": "NZ2208", "died": 180, "cause": "Heat stress", "dam_out": "Skyline", "sire_out": "Old Coal"}),
    ("Quill", "buck", NZ, "Black", 1300, "breeding", "aa BB CC Dd EE enen",
     {"tattoo": "NZ2302", "archived": 40, "dam": "Nimbus", "sire": "Basalt", "loc": "B9"}),
    ("Obsidian", "buck", NZ, "Black", 1100, "breeding", "aa Bb Cc Dd EE enen",
     {"tattoo": "NZ2301", "loc": "B1", "dam_out": "Nightshade", "sire_out": "Old Coal"}),
    ("Ember", "buck", NZ, "Red", 1050, "breeding", "Aa BB CC Dd ee enen",
     {"tattoo": "NZ2309", "loc": "B3", "dam_out": "Cinnabar", "sire_out": "Old Coal"}),
    ("Ink", "doe", NZ, "Black", 980, "breeding", "aa BB Cc Dd EE enen",
     {"tattoo": "NZ2314", "loc": "D1", "dam": "Nimbus", "sire": "Basalt"}),
    ("Frost", "buck", NZ, "REW", 950, "breeding", "aa Bb cc Dd Ee enen",
     {"tattoo": "NZ2404", "loc": "B4", "eye": "ruby", "dam_out": "Alba", "sire": "Basalt"}),
    ("Slate", "buck", NZ, "Blue", 900, "breeding", "aa BB Cc dd EE enen",
     {"tattoo": "NZ2406", "loc": "B2", "dam_out": "Skyline", "sire": "Basalt"}),
    ("Garnet", "doe", NZ, "Red", 900, "culled", "Aa BB CC Dd ee enen",
     {"tattoo": "NZ2311", "died": 90, "cull": "Poor mothering on two litters.", "dam_out": "Cinnabar", "sire": "Ember"}),
    ("Patch", "buck", NZ, "Broken Black", 880, "breeding", "aa Bb Cc Dd EE Enen",
     {"tattoo": "NZ2407", "loc": "B5", "dam_out": "Nightshade", "sire_out": "Checkers"}),
    ("Indigo", "doe", NZ, "Blue", 850, "breeding", "aa BB Cc dd EE enen",
     {"tattoo": "NZ2408", "loc": "D5", "dam": "Nimbus", "sire": "Basalt"}),
    ("Snow", "doe", NZ, "REW", 800, "breeding", "aa BB cc dd EE enen",
     {"tattoo": "NZ2411", "loc": "D12", "eye": "ruby", "dam_out": "Alba", "sire": "Frost"}),
    ("Coral", "doe", NZ, "Red", 780, "breeding", "Aa BB Cc Dd ee enen",
     {"tattoo": "NZ2412", "loc": "D8", "dam_out": "Cinnabar", "sire": "Ember"}),
    ("Shadow", "doe", NZ, "Black", 720, "breeding", "aa Bb CC Dd EE enen",
     {"tattoo": "NZ2410", "loc": "D2", "dam": "Ink", "sire": "Obsidian"}),
    ("Sierra", "doe", CAL, "Californian", 700, "breeding", "aa BB chch Dd EE enen",
     {"tattoo": "CA2403", "loc": "C1", "eye": "ruby", "dam_out": "Sunset", "sire_out": "Pacific"}),
    ("Magpie", "doe", NZ, "Broken Blue", 650, "breeding", "aa BB Cc dd EE Enen",
     {"tattoo": "NZ2416", "loc": "D15", "dam": "Indigo", "sire": "Patch"}),
    ("Azure", "doe", NZ, "Blue", 610, "breeding", "aa BB CC dd EE enen",
     {"tattoo": "NZ2418", "loc": "D6", "dam": "Indigo", "sire": "Slate"}),
    ("Pinto", "buck", NZ, "Broken Black", 600, "sold", "aa Bb Cc Dd EE Enen",
     {"tattoo": "NZ2415", "buyer": 0, "dam": "Ink", "sire": "Patch"}),
    ("Sienna", "doe", NZ, "Red", 560, "breeding", "AA BB CC DD ee enen",
     {"tattoo": "NZ2504", "loc": "D9", "dam": "Coral", "sire": "Ember"}),
    ("Mirage", "doe", CAL, "Californian", 550, "sold", "aa BB chch Dd EE enen",
     {"tattoo": "CA2410", "buyer": 2, "eye": "ruby", "dam": "Sierra", "sire_out": "Pacific"}),
    ("Onyx", "doe", NZ, "Black", 540, "breeding", "aa BB Cc DD EE enen",
     {"tattoo": "NZ2502", "loc": "D3", "dam": "Ink", "sire": "Obsidian"}),
    ("Mojave", "doe", CAL, "Californian", 520, "breeding", "aa Bb chch DD EE enen",
     {"tattoo": "CA2501", "loc": "C2", "eye": "ruby", "dam": "Sierra", "sire_out": "Pacific"}),
    ("Ivory", "doe", NZ, "REW", 500, "breeding", "aa Bb cc Dd Ee enen",
     {"tattoo": "NZ2506", "loc": "D13", "eye": "ruby", "dam": "Snow", "sire": "Frost"}),
    # Sold REW: hides chocolate (bb) and otter (at) under cc → Known rabbits goals
    ("Blizzard", "doe", NZ, "REW", 480, "sold", "ata bb cc Dd EE enen",
     {"tattoo": "NZ2503", "buyer": 1, "eye": "ruby", "dam_out": "Alba", "sire_out": "Old Coal"}),
    ("Domino", "doe", NZ, "Broken Red", 470, "breeding", "Aa BB CC Dd ee Enen",
     {"tattoo": "NZ2507", "loc": "D16", "dam_out": "Cinnabar", "sire_out": "Checkers"}),
    ("Copper", "doe", NZ, "Red", 430, "breeding", "Aa BB CC Dd ee enen",
     {"tattoo": "NZ2509", "loc": "D10", "dam": "Coral", "sire": "Ember"}),
    ("Raven", "doe", NZ, "Black", 400, "breeding", "aa BB CC Dd EE enen",
     {"tattoo": "NZ2508", "loc": "D4", "dam": "Ink", "sire": "Slate"}),
    ("Cobalt", "doe", NZ, "Blue", 380, "breeding", "aa BB Cc dd EE enen",
     {"tattoo": "NZ2511", "loc": "D7", "dam": "Indigo", "sire": "Slate"}),
    ("Sonora", "doe", CAL, "Californian", 360, "breeding", "aa BB chch Dd EE enen",
     {"tattoo": "CA2505", "loc": "C3", "eye": "ruby", "dam": "Sierra", "sire_out": "Pacific"}),
    ("Pearl", "doe", NZ, "REW", 340, "breeding", "aa BB cc Dd EE enen",
     {"tattoo": "NZ2512", "loc": "D14", "eye": "ruby", "dam": "Snow", "sire": "Frost"}),
    ("Harlequin", "doe", NZ, "Broken Black", 320, "breeding", "aa Bb CC Dd EE Enen",
     {"tattoo": "NZ2515", "loc": "D17", "dam": "Shadow", "sire": "Patch"}),
    ("Flame", "doe", NZ, "Red", 300, "breeding", "Aa BB CC Dd ee enen",
     {"tattoo": "NZ2514", "loc": "D11", "dam": "Sienna", "sire": "Ember"}),
    # Juniors converted from Ink × Patch (kindled 95 days ago)
    ("Jet", "buck", NZ, "Black", 95, "growing", "aa Bb Cc Dd EE enen", {"loc": "G1", "kit_of": "converted"}),
    ("Soot", "doe", NZ, "Black", 95, "growing", "aa BB CC Dd EE enen", {"loc": "G1", "kit_of": "converted"}),
    ("Ash", "buck", NZ, "Blue", 95, "growing", "aa Bb Cc dd EE enen", {"loc": "G2", "kit_of": "converted"}),
    ("Cinder", "buck", NZ, "Broken Black", 95, "growing", "aa BB Cc Dd EE Enen", {"loc": "G2", "kit_of": "converted"}),
    # Juniors converted from Sierra × Obsidian NZ×Californian (kindled 120 days ago)
    ("Tank", "buck", "NZ × Californian", "Black", 120, "growing", "aa BB Cch Dd EE enen",
     {"loc": "G3", "kit_of": "cross", "cross": True}),
    ("Dottie", "doe", "NZ × Californian", "Himalayan", 120, "growing", "aa Bb chc DD EE enen",
     {"loc": "G3", "kit_of": "cross", "cross": True, "eye": "ruby"}),
]
OUTSIDE = [
    ("Old Coal", "NZ black foundation buck · Kessler New Zealands"),
    ("Nightshade", "NZ black foundation doe · Kessler New Zealands"),
    ("Skyline", "NZ blue doe · Cedar Run"),
    ("Cinnabar", "NZ red doe · Northwind NZ"),
    ("Alba", "NZ REW doe · Kessler New Zealands"),
    ("Checkers", "NZ broken black buck · Northwind NZ"),
    ("Sunset", "Californian doe · Fairhaven Californians"),
    ("Pacific", "Californian buck · Fairhaven Californians"),
]
NAMES = ["Juniper", "Bramble", "Thistle", "Clover", "Hazel", "Rowan", "Maple", "Sorrel", "Briar", "Tansy",
         "Fennel", "Moss", "Wren", "Sage", "Basil", "Pepper", "Nutmeg", "Willow", "Aspen", "Cedar", "Birch",
         "Hickory", "Laurel", "Ivy", "Poppy", "Daisy", "Dusty", "Smokey", "Midnight", "Licorice", "Sable",
         "Raven", "Pewter", "Storm", "Thunder", "Misty", "Ruby", "Rusty", "Ginger", "Paprika", "Saffron",
         "Marigold", "Blaze", "Ash", "Ghost", "Snowball", "Frosty", "Pearl", "Opal", "Lily", "Ziggy", "Duke",
         "Duchess", "Baron", "Major", "Captain", "Bear", "Biscuit", "Butterscotch", "Cocoa", "Hank", "Otis"]
RABBITRY = {"Black": ("Kessler New Zealands", "KNZ"), "Blue": ("Cedar Run Meat Rabbits", "CR"),
            "Red": ("Northwind NZ", "NW"), "REW": ("Kessler New Zealands", "KNZ"),
            "Broken Black": ("Northwind NZ", "NW"), "Californian": ("Fairhaven Californians", "FC")}
OUTSIDE_SEX_WORD = {"Old Coal": "buck", "Checkers": "buck", "Pacific": "buck"}
OUTSIDE_COLOR = {"Old Coal": "Black", "Nightshade": "Black", "Skyline": "Blue", "Cinnabar": "Red", "Alba": "REW",
                 "Checkers": "Broken Black", "Sunset": "Californian", "Pacific": "Californian"}

BUYERS = [
    ("Dana Whitfield", "Whitfield Farm Rabbitry", "(717) 555-0142", "Lancaster, PA"),
    ("Marcus Ortega", "Cedar Run Meat Rabbits", "(540) 555-0187", "Winchester, VA"),
    ("Lena Haugen", "Northwind NZ", "(608) 555-0119", "Madison, WI"),
]
BREEDERS = [
    ("Tom Kessler", "Kessler New Zealands", "(330) 555-0124", "Wooster, OH"),
    ("Ruth Ellison", "Fairhaven Californians", "(410) 555-0158", "Frederick, MD"),
]


def sold_days(extra):
    return extra["buyer"] * 12 + 18


def kit_grams(age_days, curve):
    """Weekly curve with light day-to-day jitter; adult plateau after 10 weeks."""
    if age_days <= 0:
        return 55
    if age_days >= 70:
        # Ease toward ~3.2 kg at 6 months on the NZ curve (commercial fryer).
        adult_ish = curve[10] + int((age_days - 70) * 18)
        return min(adult_ish, 4500)
    wk = age_days / 7
    lo, hi = int(wk), min(10, int(wk) + 1)
    if lo < 1:
        return int(55 + (curve[1] - 55) * wk)
    if lo == hi:
        return curve[lo]
    frac = wk - lo
    return int(curve[lo] + (curve[hi] - curve[lo]) * frac)


def set_genes(rabbits_by_name, gene_map):
    count = 0
    for name, rabbit in rabbits_by_name.items():
        text = gene_map.get(name)
        if not text:
            continue
        Gene.objects.filter(rabbit=rabbit, locus__in=GENE_LOCI).delete()
        Gene.objects.bulk_create([
            Gene(rabbit=rabbit, locus=locus, genotype=g, certainty=Gene.Certainty.PROBABLE)
            for locus, g in zip(GENE_LOCI, text.split())
        ])
        count += len(GENE_LOCI)
    return count


class Command(BaseCommand):
    help = "Create or refresh the NZ demo account (demo@bramble-burrow.app)."

    def add_arguments(self, parser):
        parser.add_argument("--no-password", action="store_true",
                            help="Don't set the password: an existing account keeps its own; a new one gets none.")
        parser.add_argument("--genes-only", action="store_true",
                            help="Only (re)write genes on the existing demo rabbits; nothing else changes.")

    def handle(self, no_password=False, genes_only=False, **options):
        gene_map = {row[0]: row[6] for row in HERD}
        if genes_only:
            user = get_user_model().objects.filter(email__iexact=DEMO_EMAIL).first()
            if user is None:
                raise CommandError(f"No {DEMO_EMAIL} account; run seed_demo without --genes-only first.")
            with transaction.atomic():
                rabbits = {r.name: r for r in Rabbit.all_objects.filter(owner=user, name__in=gene_map)}
                rows = set_genes(rabbits, gene_map)
            self.stdout.write(f"Genes set on {len(rabbits)} demo rabbits ({rows} rows).")
            return
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
            user.set_unusable_password()
        user.email_confirmed = True
        user.email_confirmed_at = user.email_confirmed_at or timezone.now()
        user.is_active = True
        user.save()
        HerdSettings.objects.update_or_create(
            user=user,
            defaults={"rabbitry_name": "Hollow Creek New Zealands", "prefix": "NZ",
                      "daily_email": False, "weight_unit": "lb"},
        )
        return user, created

    def wipe(self, user):
        old_files = list(RabbitPhoto.objects.filter(
            rabbit__in=Rabbit.all_objects.filter(owner=user)).values_list("image", flat=True))
        old_files += [n for n in Litter.objects.filter(owner=user).exclude(photo="").values_list("photo", flat=True)]
        Program.objects.filter(owner=user).delete()
        for model in (Task, WaitlistEntry, Expense, Litter, Pairing, BreedingSchedule,
                      Rabbit, Contact, Location, OutsideRabbit):
            getattr(model, "all_objects", model.objects).filter(owner=user).delete()
        return old_files

    def herd(self, user, today):
        day = lambda n: today - datetime.timedelta(days=n)  # noqa: E731  (n days ago; negative = ahead)
        old_files = self.wipe(user)
        breeds = {b.name: b for b in Breed.objects.filter(name__in={NZ, CAL})}
        noise = lambda key, n, spread: ((sum(map(ord, key)) * 7 + n * 13) % (2 * spread + 1)) - spread  # noqa: E731

        # Cages and pens
        loc_codes = sorted({e["loc"] for *_, e in HERD if e.get("loc")})
        loc_notes = {"B": "Buck row · 30×36 wire", "D": "Doe row · 36×36 with nest box shelf",
                     "C": "Californian row", "G": "Grow-out pen · forage rack"}
        locs = {c: Location.objects.create(owner=user, name=f"Cage {c}", notes=loc_notes[c[0]]) for c in loc_codes}

        buyers = [Contact.objects.create(owner=user, name=n, rabbitry=r, phone=p, location=loc, is_buyer=True,
                                         notes="Buys breeding stock and fryers.") for n, r, p, loc in BUYERS]
        breeders = [Contact.objects.create(owner=user, name=n, rabbitry=r, phone=p, location=loc, is_breeder=True,
                                           notes="Foundation stock came from here.") for n, r, p, loc in BREEDERS]
        fast = BreedingSchedule.objects.create(owner=user, name="Fast rebreed (meat)", gestation_days=31,
                                               palpate_day=12, nest_box_day=27, wean_age=28, process_age=70,
                                               rebreed_days=35)

        outs = {name: OutsideRabbit.objects.create(owner=user, name=name, details=details) for name, details in OUTSIDE}

        R, gene_map = {}, {}
        for name, sex, breed, color, age, status, genes, extra in HERD:
            gene_map[name] = genes
            founder = not any(k in extra for k in ("dam", "kit_of"))
            cross = extra.get("cross")
            r = Rabbit.objects.create(
                owner=user, name=name, sex=sex, breed=breed,
                breed_type="crossbred" if cross else "purebred", purebred=None if cross else breeds.get(breed),
                color=color, color_is_standard=None if cross else True,
                eye_color=extra.get("eye", "ruby" if color == "REW" else "brown"),
                birth_date=day(age), status=status, tattoo=extra.get("tattoo", ""), line="Hollow Creek",
                death_date=day(extra["died"]) if status in ("culled", "deceased") else None,
                death_cause=extra.get("cause", "Culled" if status == "culled" else ""),
                source=(breeders[1] if breed == CAL else breeders[0]) if founder else None,
                location=locs.get(extra.get("loc")) if status not in Rabbit.FORMER else None,
                breeding_schedule=fast if name in ("Ink", "Coral", "Sierra") else None,
            )
            if cross:
                from rabbits.models import BreedShare
                for b in (NZ, CAL):
                    BreedShare.objects.create(rabbit=r, breed=breeds[b], percent=Decimal("50"))
            if extra.get("archived"):
                r.archived_at = timezone.now() - datetime.timedelta(days=extra["archived"])
                r.save(update_fields=["archived_at"])
            R[name] = r
        set_genes(R, gene_map)

        # Parents: herd rabbits as Relative rows; outside ancestors as pedigree entries
        # (with genes for a few, so the planner treats them as Known rabbits).
        parents = {}
        for name, *_, extra in HERD:
            if extra.get("kit_of") == "converted":
                extra = {**extra, "dam": "Ink", "sire": "Patch"}
            if extra.get("kit_of") == "cross":
                extra = {**extra, "dam": "Sierra", "sire": "Obsidian"}
            parents[name] = (extra.get("dam"), extra.get("sire"))
            child = R[name]
            for rel, key, pos in (("dam", "dam", "d"), ("sire", "sire", "s")):
                if extra.get(key):
                    other = R[extra[key]]
                    Relative.objects.create(rabbit=child, relationship=rel, herd_rabbit=other)
                elif extra.get(key + "_out"):
                    o = outs[extra[key + "_out"]]
                    row = Relative.objects.create(rabbit=child, relationship=rel, outside=o, breed=NZ if "NZ" in o.details else CAL,
                                                  color=OUTSIDE_COLOR[o.name])
                    PedigreeEntry.objects.create(rabbit=child, position=pos, outside=o)
                    if o.name == "Checkers":
                        Gene.objects.bulk_create([Gene(relative=row, locus=l, genotype=g) for l, g in
                                                  zip(GENE_LOCI, "aa BB CC Dd EE Enen".split())])

        photos = self.photos(R, old_files)

        def pair(doe, buck):
            return Pairing.objects.get_or_create(owner=user, doe=R[doe], buck=R[buck])[0]

        def litter(doe, buck, bred, **kw):
            kw.setdefault("palpated", bred >= 12)
            return Litter.objects.create(owner=user, pairing=pair(doe, buck), bred_on=day(bred), **kw)

        # --- Birth litters for every in-house rabbit (3–4 years of history) ---
        birth = {}
        for name, sex, breed, color, age, status, genes, extra in HERD:
            dam, sire = parents[name]
            if not (dam and sire) or extra.get("kit_of"):
                continue
            key = (dam, sire, age)
            if key not in birth:
                n = 6 + noise(name, age, 2)
                birth[key] = litter(dam, sire, age + 31, palpated=True, nest_box_in=True, kindled_on=day(age),
                                    born_alive=n, died_after=1 if n > 7 else 0, weaned=True, rebred=True,
                                    notes=f"Kept {name}; rest sold as fryers or breeding stock.")
            R[name].litter = birth[key]
            R[name].save(update_fields=["litter"])
        # Fill each long-time doe's record with past litters every ~95 days
        sires_by_color = {"Black": "Obsidian", "Blue": "Slate", "Red": "Ember", "REW": "Frost",
                          "Broken Blue": "Patch", "Broken Red": "Ember", "Broken Black": "Patch", "Californian": "Obsidian"}
        history_litters = 0
        for name, sex, breed, color, age, status, genes, extra in HERD:
            if sex != "doe" or status == "sold" or age < 320:
                continue
            taken = [l.kindled_on for l in Litter.objects.filter(pairing__doe=R[name], kindled_on__isnull=False)]
            end = extra.get("died", 0) + 130
            for kindle_back in range(age - 200, end, -95):
                kd = day(kindle_back)
                if any(abs((kd - t).days) < 60 for t in taken):
                    continue
                buck = sires_by_color.get(color, "Obsidian")
                if (R[buck].birth_date - kd).days > -200:  # buck too young then
                    buck = "Basalt" if (R["Basalt"].death_date or today) > kd else "Obsidian"
                n = 6 + noise(name, kindle_back, 3)
                litter(name, buck, kindle_back + 31, palpated=True, nest_box_in=True, kindled_on=kd,
                       born_alive=max(n, 3), born_dead=noise(name, kindle_back, 1) % 2, died_after=noise(buck, kindle_back, 1) % 2,
                       weaned=True, rebred=True, processed=True,
                       notes="Fryer litter; processed at 10–11 weeks." if breed == NZ else "Californian litter; sold as fryers.")
                history_litters += 1

        # --- Current litters: every stage ---
        # 1. Converted (Ink × Patch, broken × black): juniors Jet, Soot, Ash, Cinder
        conv = litter("Ink", "Patch", 126, nest_box_in=True, kindled_on=day(95), born_alive=6, died_after=1,
                      weaned=True, rebred=True, processed=True, converted_at=timezone.now() - datetime.timedelta(days=60),
                      notes="Broken × solid: two broken, three solid. Kept four; converted to rabbit cards.")
        conv_kits = ["Jet", "Soot", "Ash", "Cinder"]
        for i, nm in enumerate(conv_kits, 1):
            R[nm].litter = conv
            R[nm].save(update_fields=["litter"])
            LitterKit.objects.create(litter=conv, number=i, sex=R[nm].sex, color=R[nm].color, rabbit=R[nm])
        LitterKit.objects.create(litter=conv, number=5, sex="doe", color="Broken Black")
        # 2. Converted NZ×Californian (Sierra × Obsidian): Tank, Dottie
        xconv = litter("Sierra", "Obsidian", 151, nest_box_in=True, kindled_on=day(120), born_alive=7, weaned=True,
                       rebred=True, processed=True, converted_at=timezone.now() - datetime.timedelta(days=80),
                       notes="NZ×Californian hybrid vigor: 1,977 g average at 10 weeks vs ~1,810 g pure NZ.")
        for i, nm in enumerate(["Tank", "Dottie"], 1):
            R[nm].litter = xconv
            R[nm].save(update_fields=["litter"])
            LitterKit.objects.create(litter=xconv, number=i, sex=R[nm].sex, color=R[nm].color, rabbit=R[nm])
        for back, (wk, g) in zip(range(113, 49, -7), XC_CURVE.items()):
            LitterCheck.objects.create(litter=xconv, date=day(back), mode="whole", kit_count=7, grams=g,
                                       weight_kind="average", status="healthy", note=f"Week {wk} average")
        for back, (wk, g) in zip(range(88, 24, -7), NZ_CURVE.items()):
            LitterCheck.objects.create(litter=conv, date=day(back), mode="whole", kit_count=5, grams=g,
                                       weight_kind="average", status="healthy", note=f"Week {wk} average")

        # 3. Weaned, convert-pending (Magpie × Patch, En × En so one charlie)
        pending = litter("Magpie", "Patch", 74, nest_box_in=True, kindled_on=day(43), born_alive=6, weaned=True,
                         notes="Weaned and sexed. Broken × broken: one charlie, three broken, two solid.")
        for i, (sx, col) in enumerate([("doe", "Broken Blue"), ("buck", "Broken Black"), ("doe", "Charlie Blue"),
                                       ("buck", "Blue"), ("doe", "Broken Blue"), ("buck", "Black")], 1):
            LitterKit.objects.create(litter=pending, number=i, sex=sx, color=col)
        for wk in range(1, 7):
            LitterCheck.objects.create(litter=pending, date=day(43 - wk * 7), mode="whole", kit_count=6,
                                       grams=NZ_CURVE[wk] + noise("Magpie", wk, 20), weight_kind="average",
                                       status="healthy", note=f"Week {wk}")

        # 4. NZ×Californian growing kits, 5 weeks (Mojave × Slate): per-kit weights, faster than pure NZ
        xgrow = litter("Mojave", "Slate", 66, nest_box_in=True, kindled_on=day(35), born_alive=8, died_after=1, weaned=True,
                       notes="NZ×Californian: per-kit weights track the hybrid curve (faster than pure NZ).")
        # Mojave chch × Slate Cc: C ch kits show black, ch c kits the Himalayan (Californian) pattern.
        xs = [LitterKit.objects.create(litter=xgrow, number=i, sex=sx, color=col)
              for i, (sx, col) in enumerate([("doe", "Black"), ("buck", "Himalayan"), ("doe", "Black"), ("buck", "Black"),
                                             ("doe", "Himalayan"), ("buck", "Black"), ("doe", "Himalayan")], 1)]
        for wk in range(1, 6):
            chk = LitterCheck.objects.create(litter=xgrow, date=day(35 - wk * 7), mode="each", kit_count=7)
            for slot in xs:
                KitCheck.objects.create(litter_check=chk, kit=slot, grams=XC_CURVE[wk] + noise("x", slot.number * wk, 25),
                                        status="watch" if (slot.number == 4 and wk == 3) else "healthy",
                                        note="Loose stool; on hay only for a day" if (slot.number == 4 and wk == 3) else "")

        # 5. Pure NZ growing kits, 3 weeks (Indigo × Slate, blue × blue): per-kit weights
        grow = litter("Indigo", "Slate", 52, nest_box_in=True, kindled_on=day(21), born_alive=7,
                      notes="All blue (dd × dd). Weighed weekly per kit.")
        gs = [LitterKit.objects.create(litter=grow, number=i, sex=sx, color="Blue")
              for i, sx in enumerate(["doe", "buck", "doe", "buck", "doe", "buck", "doe"], 1)]
        for wk in range(1, 4):
            chk = LitterCheck.objects.create(litter=grow, date=day(21 - wk * 7), mode="each", kit_count=7)
            for slot in gs:
                small = slot.number == 7
                KitCheck.objects.create(litter_check=chk, kit=slot,
                                        grams=NZ_CURVE[wk] + noise("g", slot.number * wk, 18) - (40 if small else 0),
                                        status="watch" if small else "healthy", note="Runt; fostered extra feeds" if small else "")

        # 6. Just kindled (Coral × Ember, red × red), 2 days
        kindled = litter("Coral", "Ember", 33, nest_box_in=True, kindled_on=day(2), born_alive=8, born_dead=1,
                      notes="Red × red (both carry a): six red, two tort, one stillborn.")
        # Aa ee × Aa ee: about a quarter aa ee tort.
        for i, col in enumerate(["Red", "Red", "Tort", "Red", "Red", "Red", "Tort", "Red"], 1):
            LitterKit.objects.create(litter=kindled, number=i, color=col)
        Cover.objects.create(litter=kindled, date=day(33), time=datetime.time(7, 30), outcome="covered")
        Cover.objects.create(litter=kindled, date=day(33), time=datetime.time(18, 0), outcome="covered")
        # 7. Red × REW kindled 9 days (Ivory × Ember): reds and blacks, all carrying c
        rew = litter("Ivory", "Ember", 40, nest_box_in=True, kindled_on=day(9), born_alive=7,
                     notes="REW × red: red, tort, chestnut and black kits, every one carries c.")
        for i, col in enumerate(["Red", "Black", "Chestnut", "Tort", "Chestnut", "Black", "Red"], 1):
            LitterKit.objects.create(litter=rew, number=i, color=col)
        LitterCheck.objects.create(litter=rew, date=day(2), mode="whole", kit_count=7, grams=NZ_CURVE[1] + 5,
                                   weight_kind="average", status="healthy", note="All nursing; fat bellies.")
        # 8. Black × blue cross kindled 15 days (Raven × Slate)
        bb = litter("Raven", "Slate", 46, nest_box_in=True, kindled_on=day(15), born_alive=6,
                    notes="Black (Dd) × blue: about half blue, half black.")
        for i, col in enumerate(["Black", "Blue", "Blue", "Black", "Blue", "Black"], 1):
            LitterKit.objects.create(litter=bb, number=i, color=col)
        LitterCheck.objects.create(litter=bb, date=day(8), mode="whole", kit_count=6, grams=NZ_CURVE[1],
                                   weight_kind="average", status="healthy")
        # 9. Nest box in, due in 2 days (Shadow × Obsidian)
        nest = litter("Shadow", "Obsidian", 29, nest_box_in=True, notes="Nest box in; she is pulling fur.")
        Cover.objects.create(litter=nest, date=day(29), outcome="covered")
        Cover.objects.create(litter=nest, date=day(28), outcome="no_fall", note="Second try next morning.")
        # 10. Nest box due today (Snow × Frost: REW × REW, all REW)
        litter("Snow", "Frost", 28, notes="REW × REW: every kit will be REW.")
        # 11. Palpate due (Azure × Slate), bred 12 days ago
        palp = litter("Azure", "Slate", 12, palpated=False, notes="Palpate today.")
        Cover.objects.create(litter=palp, date=day(12), outcome="covered")
        # 12. Bred / expecting with covers (Domino × Ember: broken red × red)
        exp = litter("Domino", "Ember", 5, notes="Broken × solid red: expect about half broken.")
        Cover.objects.create(litter=exp, date=day(6), outcome="refused", note="Not ready; tried again next day.")
        Cover.objects.create(litter=exp, date=day(5), time=datetime.time(8, 0), outcome="covered")
        Cover.objects.create(litter=exp, date=day(5), time=datetime.time(17, 15), outcome="covered")
        # 13. Harlequin × Frost: broken × REW, bred 8 days ago
        litter("Harlequin", "Frost", 8, notes="Broken black × REW: half REW, rest broken or solid (c carriers).")
        # 14. Sonora × Ember (NZ×Cal), just bred
        litter("Sonora", "Ember", 2, notes="Californian × NZ red for fryers.")
        Cover.objects.create(litter=Litter.objects.get(pairing__doe=R["Sonora"], bred_on=day(2)), date=day(2), outcome="covered")

        # --- Litter photos: Frank's newborn shots by coat; the CC0 broken litter for broken pairings ---
        nb = {"red": "red-newborns.jpg", "blue": "blue-newborns.jpg", "pink": "pink-newborns.jpg",
              "broken": "broken-newborns-web.jpg", "dark": "black-doe-kit.jpg"}
        folder = Path(__file__).resolve().parents[2] / "demo_photos" / "nz"
        for lit, key in [(conv, "broken"), (pending, "broken"), (kindled, "red"), (rew, "red"), (grow, "blue"),
                         (bb, "dark"), (xgrow, "dark"), (xconv, "dark")]:
            with open(folder / nb[key], "rb") as h:
                lit.photo.save("photo.jpg", File(h), save=True)

        # --- Weights: kit series (weekly to 10 weeks), then monthly adult weights ---
        rows = []
        for name, sex, breed, color, age, status, genes, extra in HERD:
            r = R[name]
            curve = XC_CURVE if (breed != NZ) else NZ_CURVE
            adult = ADULT.get((breed, sex), ADULT[(NZ, sex)])
            stop = extra.get("died", 0) if status in ("culled", "deceased") else (sold_days(extra) if status == "sold" else 0)
            for wk in range(1, 11):
                back = age - wk * 7
                if back < stop:
                    break
                rows.append(Weight(rabbit=r, date=day(back), grams=kit_grams(wk * 7, curve) + noise(name, wk, 25),
                                   note=f"Week {wk}"))
            if age < 100:
                # Juniors: weekly from week 11 up to this week
                for wk in range(11, age // 7 + 1):
                    rows.append(Weight(rabbit=r, date=day(age - wk * 7), grams=kit_grams(wk * 7, curve) + noise(name, wk, 30),
                                       note=f"Week {wk}"))
                continue
            for back in range(stop + noise(name, 1, 6) + 6, age - 99, 30):
                a = age - back
                grams = int(curve[10] + (adult - curve[10]) * min(1.0, (a - 70) / 170)) if a < 240 else adult
                rows.append(Weight(rabbit=r, date=day(back), grams=grams + noise(name, back, 120)))
        Weight.objects.bulk_create(rows)

        # --- Photos for juniors' kit days: broken placeholder on Cinder ---
        folder = Path(__file__).resolve().parents[2] / "demo_photos" / "nz"
        ph = RabbitPhoto(rabbit=R["Cinder"], notes="Demo photo: Joel Best Obinna, CC0, via Wikimedia Commons (a broken litter at about a week).",
                         taken_at=day(90), taken_from_metadata=False)
        with open(folder / "broken-newborns-web.jpg", "rb") as h:
            ph.image.save("photo.jpg", File(h), save=False)
        ph.save()

        # --- Sales, waitlist ---
        for name, *_, status, genes, extra in HERD:
            if status != "sold":
                continue
            rabbit, buyer = R[name], buyers[extra["buyer"]]
            sold_on = day(sold_days(extra))
            rabbit.sold_on, rabbit.sold_to = sold_on, buyer
            rabbit.sale_price = Decimal("85.00" if rabbit.sex == "buck" else "75.00")
            rabbit.save(update_fields=["sold_on", "sold_to", "sale_price"])
            WaitlistEntry.objects.create(owner=user, buyer=f"{buyer.name} ({buyer.rabbitry})", reach=buyer.phone,
                                         requested_on=sold_on - datetime.timedelta(days=35), breed=rabbit.breed,
                                         sex=rabbit.sex, color=rabbit.color, status="done", deposit=Decimal("25.00"),
                                         rabbit=rabbit, notes=f"Sold {sold_on:%b} {sold_on.day}; farm pickup.")
        WaitlistEntry.objects.create(owner=user, buyer="Kate Brennan", reach="(814) 555-0176", requested_on=day(12),
                                     breed=NZ, sex="doe", color="Broken", notes="Broken NZ doe for 4-H.")
        WaitlistEntry.objects.create(owner=user, buyer="Samuel Okafor (Riverbend)", reach="(502) 555-0131",
                                     requested_on=day(6), breed=NZ, sex="buck", color="Blue", status="offered",
                                     deposit=Decimal("30.00"), rabbit=R["Ash"], notes="Offered Ash; visiting Saturday.")
        WaitlistEntry.objects.create(owner=user, buyer="Greg Lutz", reach="greg@example.com", requested_on=day(70),
                                     breed=CAL, status="cancelled", notes="Found a closer breeder.")
        WaitlistEntry.objects.create(owner=user, buyer="Maya Chen (Hilltop Homestead)", reach="(607) 555-0190",
                                     requested_on=day(20), breed=NZ, sex="", color="Red",
                                     notes="Wants a trio of red fryers for freezer camp.")

        # --- Keep/cull ---
        for name, *_, extra in HERD:
            if "cull" in extra:
                CullNote.objects.create(rabbit=R[name], date=day(extra["died"] + 2), decision="cull", reason=extra["cull"])
        for nm, dec, why in [("Jet", "keep", "Dense coat, wide shoulders; future herd buck."),
                             ("Soot", "keep", "Good depth; keep as a replacement doe."),
                             ("Ash", "undecided", "Offered to a buyer; recheck at 4 months."),
                             ("Cinder", "undecided", "Nice broken pattern; tight on hindquarters."),
                             ("Tank", "keep", "Heaviest of the cross litter at 10 weeks."),
                             ("Dottie", "cull", "Cross doe; sell as pet or freezer.")]:
            CullNote.objects.create(rabbit=R[nm], date=day(7), decision=dec, reason=why)

        # --- Health notes (some with follow-up tasks) ---
        for nm, back, kind, notes, follow in [
            ("Ink", 20, "checkup", "Nails trimmed; teeth fine; good condition before rebreeding.", None),
            ("Obsidian", 45, "treatment", "Ivermectin, whole buck row rotation.", None),
            ("Coral", 1, "checkup", "Day-after-kindling check; eating and drinking.", -3),
            ("Mojave", 14, "checkup", "Milk good; cross kits outgrowing pure NZ litters.", None),
            ("Frost", 30, "injury", "Small scratch on ear from cage wire; cleaned, wire fixed.", None),
            ("Basalt", 215, "illness", "Slowing down, softer appetite.", None),
            ("Sierra", 9, "illness", "Mild snuffles; isolated, watching.", 4),
            ("Jet", 3, "checkup", "Weaned well; on pellets, hay and willow forage.", None),
        ]:
            note = HealthNote.objects.create(rabbit=R[nm], date=day(back), kind=kind, notes=notes,
                                             follow_up_on=day(follow) if follow is not None else None)
            if follow is not None:
                t = Task.objects.create(owner=user, title=f"Follow up: {R[nm].name}", due_on=day(follow), rabbit=R[nm])
                note.task = t
                note.save(update_fields=["task"])

        # --- Tasks: overdue, due today, upcoming, done, repeating ---
        for title, back, rabbit, repeat, done in [
            ("Fix the water line on the doe row", 4, None, "", False),        # overdue
            ("Pay the feed store invoice", 6, None, "", False),               # overdue
            ("Tattoo the Magpie keepers", 1, "Magpie", "", False),           # overdue
            ("Weigh the Mojave cross litter", 0, "Mojave", "weekly", False),  # today
            ("Scrub and refill water bottles", 0, None, "daily", False),      # today
            ("Trim nails on the buck row", -5, None, "monthly", False),       # upcoming
            ("Enter the Keystone meat-pen show", -12, None, "", False),
            ("Cut fresh forage: willow and plantain", -2, None, "biweekly", False),
            ("Put the nest box in for Shadow", 3, "Shadow", "", True),         # done
            ("Order 300 lb grower pellets", 10, None, "", True),
            ("Deworm the grow-out pen", 21, None, "quarterly", True),
        ]:
            Task.objects.create(owner=user, title=title, due_on=day(back), rabbit=R.get(rabbit), repeat=repeat,
                                done_at=timezone.now() - datetime.timedelta(days=max(back - 1, 0)) if done else None)

        # --- Costs: 3½ years of feed and hay, plus vet, supplies, shows, forage ---
        ex = []
        for m in range(0, 42):
            ex.append(Expense(owner=user, date=day(m * 30 + 3), category="feed", description="100 lb NZ grower pellets (18% protein)",
                              amount=Decimal("46.50") + Decimal(m % 4), weight_lb=Decimal("100")))
            if m % 2 == 0:
                ex.append(Expense(owner=user, date=day(m * 30 + 11), category="hay", description="Timothy hay, 3 square bales",
                                  amount=Decimal("36.00"), weight_lb=Decimal("150")))
            if m % 6 == 0:
                ex.append(Expense(owner=user, date=day(m * 30 + 17), category="supplies",
                                  description="J-feeders, water bottles and nest box shavings", amount=Decimal("58.25")))
        ex += [
            Expense(owner=user, date=day(9), category="other", description="Forage: willow, plantain and dandelion from the paddock (free)", amount=Decimal("0")),
            Expense(owner=user, date=day(16), category="supplies", description="Nest box pads (12)", amount=Decimal("22.00"), litter=kindled),
            Expense(owner=user, date=day(9), category="vet", description="Vet visit: Sierra snuffles", amount=Decimal("65.00"), rabbit=R["Sierra"]),
            Expense(owner=user, date=day(45), category="vet", description="Ivermectin (buck row)", amount=Decimal("18.40")),
            Expense(owner=user, date=day(40), category="shows", description="Keystone Classic meat-pen entries", amount=Decimal("30.00")),
            Expense(owner=user, date=day(4), category="feed", description="Calf Manna top-dress for nursing does", amount=Decimal("19.99"), weight_lb=Decimal("10")),
            Expense(owner=user, date=day(25), category="other", description="Mineral blocks + forage rack for grow-out", amount=Decimal("27.50")),
            Expense(owner=user, date=day(30), category="feed", description="Black oil sunflower seed (coat conditioning)", amount=Decimal("15.00"), weight_lb=Decimal("20")),
        ]
        Expense.objects.bulk_create(ex)

        # --- Shows ---
        for nm, back, show, cls, place, of, award, leg in [
            ("Obsidian", 400, "Keystone Classic", "Senior Buck", 1, 9, "Best of Variety", True),
            ("Obsidian", 220, "Ohio State Fair", "Senior Buck", 1, 12, "Best of Breed", True),
            ("Ink", 300, "Keystone Classic", "Senior Doe", 2, 11, "", False),
            ("Slate", 160, "Lancaster Spring Show", "Senior Buck", 1, 6, "Best of Variety", True),
            ("Azure", 60, "Lancaster Spring Show", "Senior Doe", 3, 8, "", False),
        ]:
            ShowEntry.objects.create(rabbit=R[nm], show_name=show, date=day(back), location="PA",
                                     show_class=cls, placing=place, out_of=of, award=award, judge="J. Miller", leg=leg)

        # --- Old litters: converted at 6–7 weeks; every kit got a real outcome ---
        conversions = self.convert_old_litters(user, R, gene_map, buyers, breeds, today)

        # --- Full 3-generation pedigrees (14 ancestors) for every rabbit ---
        pedigree_rows = self.pedigrees(user, R, parents, outs)

        # --- Breeding programs (planner) ---
        def target(key):
            from rabbits.program_plan import TARGET_KEYS
            label, _, tgt = TARGET_KEYS[key]
            return label, tgt
        for nm, key, step, dam, sire, sex in [
            ("Black meat line", "black", "plan", "Ink", "Obsidian", "doe"),
            ("Broken black keepers", "broken-black", "breeders", None, None, "buck"),
            ("Chocolate from Blizzard", "chocolate", "goal", None, None, "any"),
            ("Black otter project", "otter", "goal", None, None, "doe"),
            ("Chestnut agouti someday", "chestnut", "goal", None, None, "doe"),
        ]:
            label, tgt = target(key)
            Program.objects.create(owner=user, name=nm, target_key=key, target_label=label, target=tgt,
                                   traits=["meat", "width"], keep_count=2, keep_sex=sex, max_coi=Decimal("12.5"),
                                   step=step, dam=R.get(dam), sire=R.get(sire))

        alive = Rabbit.objects.filter(owner=user, archived_at__isnull=True).exclude(status__in=Rabbit.FORMER)
        return {
            "rabbits": Rabbit.all_objects.filter(owner=user).count(), "in herd": alive.count(),
            "bucks": alive.filter(sex="buck").count(), "does": alive.filter(sex="doe").count(),
            "broken": alive.filter(color__startswith="Broken").count(), "californian": alive.filter(breed=CAL).count(),
            "juniors": alive.filter(status="growing").count(),
            "former": Rabbit.objects.filter(owner=user, status__in=Rabbit.FORMER).count(),
            "archived": Rabbit.all_objects.filter(owner=user, archived_at__isnull=False).count(),
            "litters": Litter.objects.filter(owner=user).count(), "past litters": history_litters,
            "weights": Weight.objects.filter(rabbit__owner=user).count(), "photos": photos + 1,
            "tasks": Task.objects.filter(owner=user).count(), "expenses": Expense.objects.filter(owner=user).count(),
            "programs": Program.objects.filter(owner=user).count(),
            "converted litters": conversions["litters"], "kit outcomes": conversions["outcomes"],
            "pedigree entries": pedigree_rows,
            "waitlist": WaitlistEntry.objects.filter(owner=user).count(),
            "locations": Location.objects.filter(owner=user).count(),
        }

    def pedigrees(self, user, R, parents, outs):
        """Write all 14 pedigree positions on every demo rabbit. Herd rabbits are
        used wherever the records reach; above that, outside ancestors (same color
        line, a rabbitry and a tattoo) fill in, generated once and reused."""
        out_parents, counter = {}, [0]

        def outside_parents(o):
            if o.pk not in out_parents:
                color = OUTSIDE_COLOR.get(o.name) or o.details.split(" · ")[0]
                rabbitry, prefix = RABBITRY.get(color, RABBITRY["Black"])
                made = []
                for sex in ("doe", "buck"):
                    counter[0] += 1
                    c = color if not (color.startswith("Broken") and sex == "doe") else color.replace("Broken ", "")
                    name = f"{NAMES[(counter[0] * 7) % len(NAMES)]} {'II' if counter[0] % 3 == 0 else ''}".strip()
                    made.append(OutsideRabbit.objects.create(
                        owner=user, name=f"{prefix} {name}",
                        details=f"{c} {'doe' if sex == 'doe' else 'buck'} · {rabbitry} · {prefix}{1000 + counter[0] * 37}"))
                    OUTSIDE_COLOR[made[-1].name] = c
                out_parents[o.pk] = tuple(made)
            return out_parents[o.pk]

        # Give the named outside ancestors a color, rabbitry and tattoo in their details.
        for name, o in outs.items():
            color = OUTSIDE_COLOR[name]
            rabbitry, prefix = RABBITRY.get(color, RABBITRY["Black"])
            o.details = f"{color} {OUTSIDE_SEX_WORD.get(name, 'doe')} · {rabbitry} · {prefix}{sum(map(ord, name)) * 7 % 900 + 100}"
            o.save(update_fields=["details"])

        def herd_parents(rabbit):
            d, s_ = parents.get(rabbit.name, (None, None)) if rabbit.name in R and R[rabbit.name].pk == rabbit.pk else (None, None)
            if d is None and s_ is None:
                d, s_ = kit_parents.get(rabbit.pk, (None, None))
            rows = {r.relationship: r for r in Relative.objects.filter(rabbit=rabbit, relationship__in=["dam", "sire"])}
            dam = R[d] if d else (rows["dam"].herd_rabbit or rows["dam"].outside) if "dam" in rows else None
            sire = R[s_] if s_ else (rows["sire"].herd_rabbit or rows["sire"].outside) if "sire" in rows else None
            return dam, sire

        cache = {}

        def both(x):
            key = (type(x).__name__, x.pk)
            if key not in cache:
                cache[key] = herd_parents(x) if isinstance(x, Rabbit) else outside_parents(x)
            return cache[key]

        kit_parents = {}
        for rel in Relative.objects.filter(rabbit__owner=user, relationship__in=["dam", "sire"], herd_rabbit__isnull=False) \
                .select_related("herd_rabbit"):
            d, s_ = kit_parents.get(rel.rabbit_id, (None, None))
            if rel.relationship == "dam":
                d = rel.herd_rabbit.name
            else:
                s_ = rel.herd_rabbit.name
            kit_parents[rel.rabbit_id] = (d, s_)

        PedigreeEntry.objects.filter(rabbit__owner=user).delete()
        rows = []
        for rabbit in Rabbit.all_objects.filter(owner=user):
            level = {"": rabbit}
            for pos in PEDIGREE_POSITIONS:
                child = level.get(pos[:-1])
                if child is None:
                    continue
                dam, sire = both(child)
                if dam is None or sire is None:
                    o = OutsideRabbit.objects.create(owner=user, name="Unknown", details="")
                    dam, sire = outside_parents(o) if dam is None and sire is None else (dam, sire)
                anc = dam if pos.endswith("d") else sire
                if anc is None:
                    continue
                level[pos] = anc
                rows.append(PedigreeEntry(rabbit=rabbit, position=pos,
                                          herd_rabbit=anc if isinstance(anc, Rabbit) else None,
                                          outside=anc if isinstance(anc, OutsideRabbit) else None))
        PedigreeEntry.objects.bulk_create(rows)
        OutsideRabbit.objects.filter(owner=user, name="Unknown", pedigree_appearances__isnull=True).delete()
        return len(rows)

    def convert_old_litters(self, user, R, gene_map, buyers, breeds, today):
        """Every litter kindled more than 42 days ago was converted at 6–7 weeks.
        Kept in-house rabbits fill their slots; the rest got an outcome: sold
        (buyer, price), culled, or grown out and processed at 10–12 weeks with a
        live weight and dressed weight (56–60% dress-out), plus dated litter notes."""
        from rabbits import planner as P
        from rabbits.models import BreedShare

        cutoff = today - datetime.timedelta(days=42)
        lit_n = outcomes = 0
        photo_by_color = {}
        for ph in RabbitPhoto.objects.filter(rabbit__owner=user, is_main=True).select_related("rabbit"):
            photo_by_color.setdefault(ph.rabbit.color.replace("Broken ", "").replace("Charlie ", ""), ph.image.name)
        cull_why = ["Pinched hindquarters.", "Malocclusion starting.", "Narrow shoulders; poor depth.",
                    "Slow grower; off feed for a week.", "Weepy eye that didn't clear."]
        new_weights, new_photos, new_genes, new_rel, new_culls, shares, new_notes = [], [], [], [], [], [], []
        litters = Litter.objects.filter(owner=user, kindled_on__lt=cutoff).order_by("kindled_on", "pairing__doe__name").select_related("pairing__doe", "pairing__buck")
        for litter in litters:
            doe, buck = litter.pairing.doe, litter.pairing.buck
            kept = list(Rabbit.all_objects.filter(owner=user, litter=litter).order_by("pk"))
            survivors = max(litter.survivors or 0, len(kept))
            litter.born_alive = max(litter.born_alive or 0, survivors + (litter.died_after or 0))
            age_days = (today - litter.kindled_on).days
            convert_day = litter.kindled_on + datetime.timedelta(days=42 + (lit_n % 8))
            litter.weaned = True
            litter.processed = age_days >= 84
            litter.rebred = True
            litter.converted_at = timezone.make_aware(datetime.datetime.combine(convert_day, datetime.time(18, 0)))
            litter.save()
            LitterKit.objects.filter(litter=litter).delete()
            day = lambda n: litter.kindled_on + datetime.timedelta(days=n)
            new_notes += [LitterNote(litter=litter, date=day(18), text="Eyes open, all out of the box and eating pellets."),
                          LitterNote(litter=litter, date=day(35), text="Weaned off the doe; moved to the grow-out pen.")]
            if age_days >= 84:
                new_notes.append(LitterNote(litter=litter, date=day(77 + lit_n % 7),
                                            text="Processing day; hay-fed grow-outs dressed out well."))
            dg = P.read_genes(dict(zip(GENE_LOCI, gene_map.get(doe.name, "").split())))
            bg = P.read_genes(dict(zip(GENE_LOCI, gene_map.get(buck.name, "").split())))
            options = sorted(P.kit_genotypes(dg, bg).items())
            cross = doe.breed != buck.breed
            for i in range(survivors):
                number = i + 1
                if i < len(kept):
                    LitterKit.objects.create(litter=litter, number=number, sex=kept[i].sex, color=kept[i].color, rabbit=kept[i])
                    continue
                # A deterministic draw from the litter's kit genotypes
                x, acc, pick = ((lit_n * 37 + i * 61) % 997) / 997, 0, options[-1][0]
                for g, f in options:
                    acc += float(f)
                    if x < acc:
                        pick = g
                        break
                color = P.phenotype(pick)
                genes = ["".join(pair) for pair in pick]
                sex = "doe" if (lit_n + i) % 2 else "buck"
                k = i - len(kept)
                if k == 0 and survivors - len(kept) >= 4:
                    fate, end_wk = "sold", 8 + lit_n % 2
                elif k == 1 and survivors - len(kept) >= 5:
                    fate, end_wk = "culled", 6 + lit_n % 2
                elif age_days < 70 + 14:
                    fate, end_wk = "growing", None
                else:
                    fate, end_wk = "processed", 10 + (lit_n + i) % 3
                end = litter.kindled_on + datetime.timedelta(days=end_wk * 7) if end_wk else None
                kit = Rabbit.objects.create(
                    owner=user, name=f"{doe.name} kit {number}", sex=sex,
                    breed="NZ × Californian" if cross else doe.breed, breed_type="crossbred" if cross else "purebred",
                    purebred=None if cross else breeds.get(doe.breed), color=color,
                    birth_date=litter.kindled_on, litter=litter, line="Hollow Creek",
                    status={"sold": "sold", "culled": "culled", "processed": "culled", "growing": "growing"}[fate],
                    death_date=end if fate in ("culled", "processed") else None,
                    death_cause={"culled": "Culled", "processed": f"Processed at {end_wk} weeks"}.get(fate, ""),
                    sold_on=end if fate == "sold" else None,
                    sold_to=buyers[(lit_n + i) % len(buyers)] if fate == "sold" else None,
                    sale_price=Decimal(35 + (lit_n % 6) * 5) if fate == "sold" else None,
                )
                LitterKit.objects.create(litter=litter, number=number, sex=sex, color=color, rabbit=kit)
                if cross:
                    shares += [BreedShare(rabbit=kit, breed=breeds[NZ], percent=Decimal("50")),
                               BreedShare(rabbit=kit, breed=breeds[CAL], percent=Decimal("50"))]
                new_rel += [Relative(rabbit=kit, relationship="dam", herd_rabbit=doe),
                            Relative(rabbit=kit, relationship="sire", herd_rabbit=buck)]
                new_genes += [Gene(rabbit=kit, locus=l, genotype=g, certainty=Gene.Certainty.PROBABLE)
                              for l, g in zip(GENE_LOCI, genes)]
                curve = XC_CURVE if cross else NZ_CURVE
                last_wk = end_wk or min(age_days // 7, 26)
                for wk in range(1, last_wk + 1):
                    grams = kit_grams(wk * 7, curve) + (((lit_n * 11 + i) * 13 + wk * 7) % 61) - 30
                    note = f"Week {wk}"
                    if fate == "processed" and wk == end_wk:
                        note = "Live weight at processing"
                        kit.dressed_grams = round(grams * (0.56 + ((lit_n * 11 + i) % 5) / 100))
                        kit.save(update_fields=["dressed_grams"])
                    new_weights.append(Weight(rabbit=kit, date=litter.kindled_on + datetime.timedelta(days=wk * 7),
                                              grams=grams, note=note))
                if fate in ("culled", "processed"):
                    why = cull_why[(lit_n + i) % len(cull_why)] if fate == "culled" else \
                        f"Grown out for meat; processed at {end_wk} weeks."
                    new_culls.append(CullNote(rabbit=kit, date=end, decision="cull", reason=why))
                base = color.replace("Broken ", "").replace("Charlie ", "")
                name = photo_by_color.get(base) or photo_by_color.get("Black")
                if name:
                    new_photos.append(RabbitPhoto(rabbit=kit, image=name, is_main=True, taken_at=litter.kindled_on +
                                                  datetime.timedelta(days=35)))
                outcomes += 1
            lit_n += 1
        Weight.objects.bulk_create(new_weights)
        Gene.objects.bulk_create(new_genes)
        Relative.objects.bulk_create(new_rel)
        CullNote.objects.bulk_create(new_culls)
        BreedShare.objects.bulk_create(shares)
        RabbitPhoto.objects.bulk_create(new_photos)
        LitterNote.objects.bulk_create(new_notes)
        return {"litters": lit_n, "outcomes": outcomes}

    def photos(self, rabbits, old_files):
        """Main photo per rabbit from rabbits/demo_photos/nz, matched to its color.
        Frank Dixon's own photos need no credit; web photos carry a "Credit:" note,
        shown behind the photo's Credit badge."""
        from django.core.files.storage import default_storage
        from django.db import transaction as tx

        from rabbits.renditions import delete_renditions

        for name in old_files:
            tx.on_commit(lambda n=name: (default_storage.delete(n), delete_renditions(default_storage, n)))
        folder = Path(__file__).resolve().parents[2] / "demo_photos" / "nz"
        pool = {}
        for c in json.loads((folder / "attribution.json").read_text()):
            if "newborn" in c["file"]:
                continue
            pool.setdefault(c["color"], []).append(c)
        used, count = {}, 0
        for rabbit in rabbits.values():
            base = rabbit.color.replace("Broken ", "").replace("Charlie ", "")
            key = {"Himalayan": "Californian"}.get(base, base)
            options = pool.get(key) or pool["Black"]
            pick = options[used.get(key, 0) % len(options)]
            used[key] = used.get(key, 0) + 1
            notes = "" if pick["license"] == "Owned" else f"Demo photo: {pick['author']}, {pick['license']}, via Wikimedia Commons ({pick['source']})."
            if rabbit.color.startswith("Broken") and not notes:
                notes = "Stand-in photo of a solid rabbit of the same color."
            taken = min(timezone.localdate() - datetime.timedelta(days=20), rabbit.birth_date + datetime.timedelta(days=240))
            photo = RabbitPhoto(rabbit=rabbit, is_main=True, notes=notes, taken_at=max(taken, rabbit.birth_date),
                                uploaded_at=timezone.now() - datetime.timedelta(days=(timezone.localdate() - max(taken, rabbit.birth_date)).days))
            with open(folder / pick["file"], "rb") as handle:
                photo.image.save("photo.jpg", File(handle), save=False)
            photo.save()
            count += 1
        return count

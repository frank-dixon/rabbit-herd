"""Seed each breed's recognized colors.

Sources, read 2026-10-11:
- ARBA breeds: the American Rabbit Breeders Association's recognized breed
  pages (https://arba.net/recognized-breeds/) and the 2026 ARBA Breed
  Identification Guide, which list each breed's recognized varieties. The
  paid Standard of Perfection itself was not available, so a variety added
  very recently could be missing here.
- BRC-only breeds: the British Rabbit Council Breed Standards 2021-2025
  (https://www.thebritishrabbitcouncil.org/breed-standards.php).

Each breed gets one of two things:
- colors: the recognized colors in the standard's order. "name" is what is
  saved on a rabbit; "hint" is a short description for newcomers.
- any_color: True when the standard recognizes colors by group (for
  example Holland Lop or Netherland Dwarf), so the list is too long and
  changes too often to offer as choices. Keepers type those colors in.

The data lives in this migration, not in app code, so later edits to app
code cannot change what an old migration does.
"""

from django.db import migrations


def c(name, hint=""):
    return {"name": name, "hint": hint}


COLORS = {
    # ARBA
    "American": [c("Blue"), c("White", "Ruby-eyed white")],
    "American Chinchilla": [c("Chinchilla", "Slate-blue base, pearl band, black-tipped coat")],
    "American Sable": [c("Sable", "Sepia brown, darkest on the face, ears, back and feet")],
    "Argente Brun": [c("Brown argente", "Silvered coat over a brown undercolor")],
    "Belgian Hare": [c("Chestnut", "Rich red with black ticking"), c("Black"), c("Black tan", "Black with tan markings")],
    "Beveren": [c("Black"), c("Blue"), c("White", "Blue-eyed white")],
    "Blanc de Hotot": [c("White with black eye bands", "Pure white with a thin black ring around each eye")],
    "Blue Holicer": [c("Blue")],
    "Britannia Petite": [
        c("Black"), c("Black otter", "Black with a cream belly"), c("Chestnut agouti"),
        c("Ruby-eyed white"), c("Sable marten", "Sable with silver-white points"),
    ],
    "Californian": [c("White with black points", "White body with black nose, ears, feet and tail")],
    "Champagne d'Argent": [c("Champagne", "Silver coat over a slate-blue undercolor")],
    "Checkered Giant": [c("Black", "White with black markings"), c("Blue", "White with blue markings")],
    "Cinnamon": [c("Cinnamon", "Russet orange with smoke-gray ticking")],
    "Creme d'Argent": [c("Creme", "Creamy white coat over an orange undercolor")],
    "Czech Frosty": [c("Frosty", "Pale frosted coat with darker points")],
    "Dutch": [
        c("Black"), c("Blue"), c("Chinchilla"), c("Chocolate"), c("Gray"),
        c("Steel gray"), c("Tortoise", "Orange with smoky shading"),
    ],
    "Dwarf Hotot": [
        c("White with black eye bands", "Pure white with a thin black ring around each eye"),
        c("White with chocolate eye bands", "Pure white with a thin chocolate ring around each eye"),
    ],
    # Recently recognized; check new varieties against the next ARBA guide.
    "Dwarf Papillon": [c("Black", "White with black butterfly markings"), c("Chocolate", "White with chocolate butterfly markings")],
    "English Spot": [
        c("Black"), c("Blue"), c("Chocolate"), c("Gold"), c("Gray"), c("Lilac"), c("Tortoise"),
    ],
    "Flemish Giant": [
        c("Black"), c("Blue"), c("Fawn"), c("Light gray"), c("Sandy"), c("Steel gray"), c("White"),
    ],
    "Florida White": [c("White", "Pure white with ruby eyes")],
    "Giant Chinchilla": [c("Chinchilla", "Slate-blue base, pearl band, black-tipped coat")],
    "Harlequin": [c("Japanese", "Orange alternating with black, blue, chocolate or lilac"), c("Magpie", "White alternating with black, blue, chocolate or lilac")],
    "Havana": [c("Black"), c("Blue"), c("Broken"), c("Chocolate"), c("Lilac")],
    "Himalayan": [c("Black", "White with black points"), c("Blue", "White with blue points"), c("Chocolate", "White with chocolate points"), c("Lilac", "White with lilac points")],
    "Lilac": [c("Lilac", "Even pinkish dove-gray")],
    # Inferred: ARBA's Mini Californian page shows only the Californian
    # pattern, but its variety list was not published when this was written.
    "Mini Californian": [c("White with black points", "White body with black nose, ears, feet and tail")],
    "New Zealand": [c("White", "Ruby-eyed white"), c("Red"), c("Black"), c("Blue"), c("Broken")],
    "Palomino": [c("Golden"), c("Lynx")],
    "Polish": [
        c("Black"), c("Blue"), c("Blue-eyed white"), c("Broken"), c("Chocolate"), c("Lilac"), c("Ruby-eyed white"),
    ],
    "Rhinelander": [c("Black", "White with black and orange markings"), c("Blue", "White with blue and fawn markings")],
    "Silver": [c("Black", "Black, evenly silvered"), c("Brown", "Brown, evenly silvered"), c("Fawn", "Fawn, evenly silvered")],
    "Silver Fox": [c("Black"), c("Blue"), c("Chocolate"), c("Lilac")],
    "Silver Marten": [c("Black"), c("Blue"), c("Chocolate"), c("Sable")],
    "Standard Chinchilla": [c("Chinchilla", "Slate-blue base, pearl band, black-tipped coat")],
    "Tan": [c("Black"), c("Blue"), c("Chocolate"), c("Lilac")],
    "Thrianta": [c("Orange-red", "Deep, even orange-red")],
    # BRC
    "Alaska": [c("Black")],
    "Argente Bleu": [c("Blue argente", "Silvered coat over a blue undercolor")],
    "Argente Noir": [c("Black argente", "Silvered coat over a black undercolor")],
    "Beige": [c("Beige", "Sandy beige with faint ticking")],
    "Blanc de Bouscat": [c("White", "Ruby-eyed white")],
    "Blanc de Termonde": [c("White", "Ruby-eyed white")],
    "Chinchilla Giganta": [c("Chinchilla", "Slate-blue base, pearl band, black-tipped coat")],
    "Deilenaar": [c("Red-brown agouti", "Warm red-brown with black ticking")],
    "Golden Glavcot": [c("Golden", "Golden coat over a slate-blue undercolor")],
    "Hulstlander": [c("White", "Blue-eyed white")],
    "Meissner Lop": [c("Black", "Black, evenly silvered"), c("Blue", "Blue, evenly silvered"), c("Brown", "Brown, evenly silvered"), c("Fawn", "Fawn, evenly silvered")],
    "Perlfee": [c("Greyish blue", "Light, medium or dark shades of grey-blue")],
    "Pointed Beveren": [c("Black", "White-tipped black"), c("Blue", "White-tipped blue"), c("Brown", "White-tipped brown"), c("Lilac", "White-tipped lilac")],
    "Sallander": [c("Pearl", "Pearl with a charcoal veil")],
    "Siamese Sable": [c("Light"), c("Medium"), c("Dark")],
    "Siberian": [c("Black"), c("Blue"), c("Brown"), c("Lilac")],
    "Smoke Pearl": [c("Marten smoke pearl", "With white belly and markings"), c("Siamese smoke pearl", "Shaded, without white markings")],
    "Squirrel": [c("Squirrel", "Blue chinchilla")],
    "Sussex": [c("Gold"), c("Cream")],
    "Thuringer": [c("Chamois", "Yellow-ochre with a sooty veil")],
    "Vienna": [c("Black"), c("Blue"), c("Brown"), c("Blue-eyed white")],
    "Wheaten": [c("Wheaten", "Rich wheaten with a pale belly")],
    "Wheaten Lynx": [c("Wheaten lynx", "Orange shot with silver")],
}

ANY_COLOR = [
    # ARBA: colors recognized by group.
    "American Fuzzy Lop", "English Angora", "English Lop", "French Angora", "French Lop",
    "Giant Angora", "Holland Lop", "Jersey Wooly", "Lionhead", "Mini Lop", "Mini Rex",
    "Mini Satin", "Netherland Dwarf", "Rex", "Satin", "Satin Angora",
    # BRC: colors recognized by group.
    "Astrex", "British Giant", "Cashmere Lop", "Continental Giant", "Dwarf Lop",
    "Giant Papillon", "Miniature Cashmere Lop", "Miniature Lion Lop", "Opossum", "Swiss Fox",
]


def seed(apps, schema_editor):
    Breed = apps.get_model("rabbits", "Breed")
    for breed in Breed.objects.all():
        if breed.name in COLORS:
            breed.colors, breed.any_color = COLORS[breed.name], False
        elif breed.name in ANY_COLOR:
            breed.colors, breed.any_color = [], True
        else:
            continue
        breed.save(update_fields=["colors", "any_color"])


def unseed(apps, schema_editor):
    apps.get_model("rabbits", "Breed").objects.update(colors=[], any_color=False)


class Migration(migrations.Migration):
    dependencies = [("rabbits", "0006_breed_colors")]
    operations = [migrations.RunPython(seed, unseed)]

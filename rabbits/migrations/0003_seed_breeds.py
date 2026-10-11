"""Seed the breed catalog.

ARBA breeds come from the American Rabbit Breeders Association's list of
recognized breeds (https://arba.net/recognized-breeds/, read 2026-10-10).
That list has 53 rabbit breeds; the Mini Californian is the 53rd. Cavies
are on the same page but are not rabbits.

Other breeds are recognized by the British Rabbit Council
(https://www.thebritishrabbitcouncil.org/rabbit-breeds.php and its Breed
Standards) but not by ARBA. Breeds that share a name with an ARBA breed
are left out to avoid two entries with one name.

The list lives in this migration, not in app code, so later edits to app
code cannot change what an old migration does.
"""

from django.db import migrations

ARBA_BREEDS = [
    "American",
    "American Chinchilla",
    "American Fuzzy Lop",
    "American Sable",
    "Argente Brun",
    "Belgian Hare",
    "Beveren",
    "Blanc de Hotot",
    "Blue Holicer",
    "Britannia Petite",
    "Californian",
    "Champagne d'Argent",
    "Checkered Giant",
    "Cinnamon",
    "Creme d'Argent",
    "Czech Frosty",
    "Dutch",
    "Dwarf Hotot",
    "Dwarf Papillon",
    "English Angora",
    "English Lop",
    "English Spot",
    "Flemish Giant",
    "Florida White",
    "French Angora",
    "French Lop",
    "Giant Angora",
    "Giant Chinchilla",
    "Harlequin",
    "Havana",
    "Himalayan",
    "Holland Lop",
    "Jersey Wooly",
    "Lilac",
    "Lionhead",
    "Mini Californian",
    "Mini Lop",
    "Mini Rex",
    "Mini Satin",
    "Netherland Dwarf",
    "New Zealand",
    "Palomino",
    "Polish",
    "Rex",
    "Rhinelander",
    "Satin",
    "Satin Angora",
    "Silver",
    "Silver Fox",
    "Silver Marten",
    "Standard Chinchilla",
    "Tan",
    "Thrianta",
]

OTHER_BREEDS = [
    "Alaska",
    "Argente Bleu",
    "Argente Noir",
    "Astrex",
    "Beige",
    "Blanc de Bouscat",
    "Blanc de Termonde",
    "British Giant",
    "Cashmere Lop",
    "Chinchilla Giganta",
    "Continental Giant",
    "Deilenaar",
    "Dwarf Lop",
    "Giant Papillon",
    "Golden Glavcot",
    "Hulstlander",
    "Meissner Lop",
    "Miniature Cashmere Lop",
    "Miniature Lion Lop",
    "Opossum",
    "Perlfee",
    "Pointed Beveren",
    "Sallander",
    "Siamese Sable",
    "Siberian",
    "Smoke Pearl",
    "Squirrel",
    "Sussex",
    "Swiss Fox",
    "Thuringer",
    "Vienna",
    "Wheaten",
    "Wheaten Lynx",
]


def seed(apps, schema_editor):
    Breed = apps.get_model("rabbits", "Breed")
    for registry, names in (("arba", ARBA_BREEDS), ("other", OTHER_BREEDS)):
        for name in names:
            Breed.objects.update_or_create(name=name, defaults={"registry": registry})


def unseed(apps, schema_editor):
    Breed = apps.get_model("rabbits", "Breed")
    Breed.objects.filter(name__in=ARBA_BREEDS + OTHER_BREEDS).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("rabbits", "0002_breed"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]

"""The two app marks (Settings > Appearance > App icon): thin line drawings,
no tile. S1 is the default and the one used for the favicon and PWA icons."""

MARKS = {
    "s1": {"viewbox": '0 0 104 104', "transform": 'translate(-1 3.5)', "paths": ['M44 86H18C8 85 9 48 36 42C52 39 62 48 66 56C64 44 48 28 50 20C55 22 72 44 71 57C86 58 93 66 92 73C91 77 87 80 82 80C78 81 80 80 80 86H88', 'M14 92H92', 'M14.0 97H22.0M26.0 97H28.0M32.0 97H48.0M52.0 97H56.0M60.0 97H62.0M66.0 97H92.0']},
    "g2": {"viewbox": '0 0 108 108', "transform": 'translate(2 -3)', "paths": ['M74 88C76 84 72 78 70 66C69 58 70 54 72 52L86 48C90 46 90 42 86 40L76 34L70 30C64 18 58 8 54 6C52 10 56 22 64 36C58 24 50 14 44 12C42 16 48 28 58 40C46 40 32 44 24 56C18 66 18 80 26 88H40', 'M22 94H86', 'M22 99H28M32 99H34M38 99H52M56 99H60M64 99H66M70 99H86']},
}
DEFAULT = "s1"


def mark(key):
    return MARKS.get(key) or MARKS[DEFAULT]

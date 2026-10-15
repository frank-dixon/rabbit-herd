"""Writes assets/themes.css and pages/theme_data.py from the approved palettes
(Light = revised Direction 2; Dark, Medium, Warm and Cool boards A-C; Heritage Show).
Derived tokens are oklab mixes, as on the boards. Run: python scripts/gen_themes.py"""
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# key, label, dark?, bg, surface (search/hover well), ink, muted, accent, on-accent
PALETTES = [
    ("light", "Light", False, "#FAFAF9", "#F1F2F0", "#1A1F1C", "#6B736E", "#22573B", "#FFFFFF"),
    # Heritage Show (B1): navy ink/accent, cream canvas, crimson danger. Square corners + Zilla Slab are in heritage.css.
    ("heritage", "Heritage Show", False, "#F6F3EC", "#EEF0F5", "#1B2A4A", "#5A6478", "#1B2A4A", "#FFFEFA"),
    ("dark-a", "Evergreen night", True, "#0F1512", "#18201C", "#E8EEEA", "#8E9A93", "#5CC48A", "#08140D"),
    ("dark-b", "Midnight and mint", True, "#0E1117", "#171C25", "#E6EAF0", "#8B93A1", "#4FD1A1", "#04150E"),
    ("dark-c", "Deep moss and amber", True, "#12140F", "#1C1F18", "#ECEDE6", "#9A9D90", "#E2A85A", "#1A1206"),
    ("med-a", "Slate", True, "#2A2F36", "#343A42", "#EEF1F4", "#A3ABB5", "#6FCF97", "#0B1F13"),
    ("med-b", "Charcoal sage", True, "#2B2E2C", "#363A37", "#F0F2EF", "#A7ADA8", "#8FD3A8", "#0E2016"),
    ("med-c", "Graphite and sky", True, "#262B33", "#303641", "#EDF0F5", "#9FA8B6", "#7AB8F5", "#0A1A2B"),
    ("warm-a", "Cream and forest", False, "#FAF6EE", "#F1EBDF", "#231F1A", "#7A7266", "#22573B", "#FFFFFF"),
    ("warm-b", "Oat and terracotta", False, "#F7F2EA", "#EDE5D8", "#2A211B", "#7D7064", "#B4532A", "#FFFFFF"),
    ("warm-c", "Linen and olive", False, "#F6F4EC", "#EBE8DC", "#22241C", "#74766A", "#56662B", "#FFFFFF"),
    ("cool-a", "Mist and forest", False, "#F6F8FA", "#ECF0F4", "#141A22", "#66707D", "#22573B", "#FFFFFF"),
    ("cool-b", "Blue-gray and indigo", False, "#F5F7FA", "#EAEEF4", "#131826", "#636B7D", "#4353D6", "#FFFFFF"),
    ("cool-c", "Fog and teal", False, "#F4F7F7", "#E8EEEE", "#142021", "#627173", "#13786E", "#FFFFFF"),
]
GROUPS = {"light": "Light", "heritage": "Heritage", "dark": "Dark", "med": "Medium", "warm": "Warm", "cool": "Cool"}
# semantic: dark-mode fg, light bg, light fg
SEM = {"g": ("#3FB27F", "#7FDCA6", "#DDF1E3", "#1A6B3E"), "b": ("#4C8DF0", "#9CC2FF", "#E1ECFB", "#2457A6"),
       "y": ("#E0A93B", "#F2CB7C", "#FBF0D5", "#8A5A00"), "r": ("#E5574B", "#FF9C92", "#FBE3E1", "#A3271E")}


def hex2(c):
    return [int(c[i:i + 2], 16) / 255 for i in (1, 3, 5)]


def lin(v):
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def unlin(v):
    v = max(0.0, min(1.0, v))
    return 12.92 * v if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055


def oklab(c):
    r, g, b = (lin(x) for x in hex2(c))
    l = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    m = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    s = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    return (0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s, 1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
            0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s)


def from_oklab(L, a, b):
    l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s = (L - 0.0894841775 * a - 1.2914855480 * b) ** 3
    rgb = (4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s, -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
           -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s)
    return "#" + "".join(f"{round(unlin(v) * 255):02X}" for v in rgb)


def mix(c, pct, base):
    x, y = oklab(c), oklab(base)
    t = pct / 100
    return from_oklab(*(a * t + b * (1 - t) for a, b in zip(x, y)))


def lum(c):
    r, g, b = (lin(x) for x in hex2(c))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    x, y = sorted((lum(a), lum(b)), reverse=True)
    return (x + 0.05) / (y + 0.05)


def nudge(c, toward, *against, target=4.6):
    """The board color, pulled toward `toward` in 2% steps until it clears AA
    (with a little margin) on every background it sits on."""
    out, pct = c, 0
    while min(contrast(out, b) for b in against) < target and pct < 60:
        pct += 2
        out = mix(toward, pct, c)
    return out


def tokens(dark, bg, surf, ink, mu, acc, on):
    mu = nudge(mu, ink, bg, surf, "#FFFFFF" if not dark else surf)
    acc = nudge(acc, ink, bg, "#FFFFFF" if not dark else surf)
    t = {
        "canvas": bg, "surface": surf if dark else "#FFFFFF", "well": surf, "side": bg,
        "line": mix(ink, 12 if dark else 9, bg), "line-soft": mix(ink, 8 if dark else 6, bg), "hover": mix(ink, 5 if dark else 3, bg),
        "ink": ink, "ink-2": mix(ink, 80, bg), "muted-base": mu, "faint": mix(mu, 75, bg),
        "accent": acc, "accent-hover": mix(acc, 88, "#FFFFFF" if dark else "#000000"), "on-accent": on, "accent-soft": mix(acc, 16, bg),
        "field": mix(ink, 30, bg), "photo-1": mix(ink, 9, bg), "photo-2": mix(ink, 15, bg), "track": mix(ink, 10, bg), "pill": mix(ink, 8, bg),
        "pos": "#6FD39B" if dark else "#1E7A46",
    }
    for k, (d, df, l, lf) in SEM.items():
        t[k + "-soft"] = mix(d, 22, bg) if dark else l
        t[k + "-ink"] = df if dark else lf
    t["accent"] = nudge(t["accent"], ink, bg, t["surface"], t["accent-soft"])
    t["second"], t["second-ink"], t["second-soft"] = t["b-ink"], t["b-ink"], t["b-soft"]
    t["danger"], t["warn"] = t["r-ink"], t["y-ink"]
    return t


def build():
    css = ["/* Generated by scripts/gen_themes.py: palettes, each with its own fixed mode.\n   Light is the default (revised Direction 2). Do not edit by hand. */\n"]
    data, report = [], []
    for key, label, dark, bg, surf, ink, mu, acc, on in PALETTES:
        t = tokens(dark, bg, surf, ink, mu, acc, on)
        if key == "heritage":
            # Match mood board B1: cream surface, crimson danger, gold warn, navy second.
            t["surface"] = "#FFFEFA"
            t["well"] = "#EEF0F5"
            t["side"] = "#EEF0F5"
            t["r-soft"], t["r-ink"] = "#F5E0DE", "#9B2C2C"
            t["danger"] = "#9B2C2C"
            t["y-soft"], t["y-ink"] = "#F3E8C8", "#6B4E12"
            t["warn"] = "#6B4E12"
            t["g-soft"], t["g-ink"] = "#DCE8DC", "#1E4D32"
            t["b-soft"], t["b-ink"] = "#DCE2EF", "#1B2A4A"
            t["second"], t["second-ink"], t["second-soft"] = t["b-ink"], t["b-ink"], t["b-soft"]
            t["pill"] = "#E8E4D8"
        sel = 'html[data-theme="light"], :root:not([data-theme])' if key == "light" else f'html[data-theme="{key}"]'
        css.append(sel + " {\n  color-scheme: " + ("dark" if dark else "light") + ";\n" + "".join(f"  --{k}: {v};\n" for k, v in t.items()) + "}\n")
        data.append((key, label, GROUPS[key.split("-")[0]], dark, bg, t["surface"], t["accent"], ink))
        mu, acc = t["muted-base"], t["accent"]
        checks = {"muted/canvas": contrast(mu, bg), "muted/surface": contrast(mu, t["surface"]), "muted/well": contrast(mu, surf),
                  "ink/canvas": contrast(ink, bg), "accent/canvas": contrast(acc, bg), "accent/surface": contrast(acc, t["surface"]),
                  "on-accent/accent": contrast(on, acc), "accent/accent-soft": contrast(acc, t["accent-soft"]),
                  **{f"{k}-pill": contrast(t[k + "-ink"], t[k + "-soft"]) for k in SEM}}
        report.append((key, {k: round(v, 2) for k, v in checks.items()}))
    css.append("html { --muted: var(--muted-base); }\n")
    (ROOT / "assets" / "themes.css").write_text("\n".join(css))
    (ROOT / "pages" / "theme_data.py").write_text(
        '"""Generated by scripts/gen_themes.py. (key, label, group, dark, canvas, surface, accent, ink)."""\n\nTHEMES = [\n'
        + "".join(f"    {d!r},\n" for d in data) + "]\n")
    return report


if __name__ == "__main__":
    for key, r in build():
        low = {k: v for k, v in r.items() if v < 4.5}
        print(key, "AA ok" if not low else f"BELOW AA {low}", min(r.values()))

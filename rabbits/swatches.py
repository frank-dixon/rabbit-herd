"""A small CSS background per coat color name, for goal and predicted-color swatches."""

INK, BLUE, WHITE = "#1d1d1f", "#6E7C8C", "#F3F1EC"
BASE = {
    "black": INK, "blue": BLUE, "chocolate": "#5A3A2A", "lilac": "#B3A9AE", "chestnut": "#8A5A3B",
    "opal": "#A9A08C", "orange": "#D98A3A", "red": "#B5532C", "fawn": "#D9B98A", "white": WHITE,
    "ruby-eyed white": WHITE, "rew": WHITE, "lynx": "#C9B8A6", "squirrel": "#9AA3AD", "sable": "#5B4636",
    "seal": "#3A2E28", "smoke": "#7D7672", "agouti": "#8A6A4B", "steel": "#3D3F44", "cream": "#EAD9B5",
    "californian": f"linear-gradient(135deg,{WHITE} 60%,{INK} 60%)",
}


def swatch(name):
    """CSS background for a color name like "Broken black", "Black otter" or "Himalayan (blue points)"."""
    text = (name or "").lower().strip()
    if not text:
        return "var(--pill)"
    if text.startswith("himalayan"):
        point = BLUE if "blue" in text else BASE["chocolate"] if "chocolate" in text else INK
        return f"linear-gradient(135deg,{WHITE} 60%,{point} 60%)"
    if text.startswith("broken"):
        return f"repeating-linear-gradient(45deg,{base(text[6:])} 0 6px,{WHITE} 6px 12px)"
    if text.endswith("otter"):
        return f"linear-gradient(135deg,{base(text[:-5])} 55%,#E9C79A 55%)"
    if "tortoise" in text or text.startswith("tort"):
        return f"linear-gradient(135deg,#C99A62,{base(text.replace('tortoise', ''))})"
    return base(text)


def base(text):
    text = text.strip()
    if text in BASE:
        return BASE[text]
    for word in text.split():
        if word in BASE:
            return BASE[word]
    return "#C8C6C0"

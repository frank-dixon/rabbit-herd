"""The Flow view: a two-generation band chart drawn as plain SVG on the
server. Band height is each outcome's share of kits; the kept target band
runs on into the G2 pairing, the rest stop."""

W, H, TOP = 1000, 300, 14
NODE = 12
X_G0, X_G1, X_G2, X_K2 = 0, 330, 640, W - NODE
GAP = 8


def stack(rows, top=TOP, height=H - 2 * TOP):
    """[(row, y, h)] stacked top to bottom with gaps."""
    usable = height - GAP * max(len(rows) - 1, 0)
    out, y = [], top
    for row in rows:
        h = max(float(row["chance"]) * usable, 2)
        out.append((row, y, h))
        y += h + GAP
    return out


def ribbon(x1, y1a, y1b, x2, y2a, y2b):
    """A filled band from a vertical span at x1 to one at x2."""
    m = (x1 + x2) / 2
    return (f"M{x1:.1f},{y1a:.1f} C{m:.1f},{y1a:.1f} {m:.1f},{y2a:.1f} {x2:.1f},{y2a:.1f} "
            f"L{x2:.1f},{y2b:.1f} C{m:.1f},{y2b:.1f} {m:.1f},{y1b:.1f} {x1:.1f},{y1b:.1f} Z")


def declutter(labels, line=20):
    """Push labels in the same column down so none overlap; a label with a
    second line takes more room."""
    last = {}
    for label in labels:
        column = label.get("anchor", "start")
        if column in last:
            prev = last[column]
            label["y"] = max(label["y"], prev["y"] + line * (1.8 if prev["sub"] else 1))
        last[column] = label


def flow_svg(plan, program):
    g1 = stack(plan["g1"]["rows"])
    full = H - 2 * TOP
    shapes, labels = [], []
    # G0 to each G1 band: slices of the G0 node in band order.
    y0 = TOP
    for row, y, h in g1:
        share = float(row["chance"]) * full
        shapes.append({"d": ribbon(X_G0 + NODE, y0, y0 + share, X_G1, y, y + h), "cls": f"pf-{row['shade']}", "kept": row["target"], "band": True})
        shapes.append({"rect": (X_G1, y, NODE, h), "cls": f"pf-{row['shade']}", "node": True})
        labels.append({"x": X_G1 + NODE + 10, "y": y + min(h / 2, 18) + 4, "name": row["name"], "pct": row["pct"],
                       "sub": f"keep {program.keep_count} {plan['keep_word']}" if row["target"] else "", "target": row["target"]})
        y0 += share
    shapes.insert(0, {"rect": (X_G0, TOP, NODE, full), "cls": "pf-node", "node": True})
    g2 = plan.get("g2")
    if g2:
        targets = [(row, y, h) for row, y, h in g1 if row["target"]]
        if targets:
            ya, yb = targets[0][1], targets[-1][1] + targets[-1][2]
            shapes.append({"d": ribbon(X_G1 + NODE, ya, yb, X_G2, TOP, TOP + full), "cls": "pf-carry", "band": True, "kept": True})
        shapes.append({"rect": (X_G2, TOP, NODE, full), "cls": "pf-planned", "node": True, "dashed": True})
        y0 = TOP
        for row, y, h in stack(g2["rows"]):
            share = float(row["chance"]) * full
            shapes.append({"d": ribbon(X_G2 + NODE, y0, y0 + share, X_K2, y, y + h), "cls": f"pf-{row['shade']}", "band": True, "kept": row["target"]})
            shapes.append({"rect": (X_K2, y, NODE, h), "cls": f"pf-{row['shade']}", "node": True})
            labels.append({"x": X_K2 - 10, "y": y + min(h / 2, 18) + 4, "name": row["name"], "pct": row["pct"], "anchor": "end",
                           "sub": f"goal: keep {program.keep_count}" if row["target"] else ("no charlies" if plan["charlie_tip"] and not row["name"].startswith("Charlie") and row is g2["rows"][-1] else ""),
                           "target": row["target"]})
            y0 += share
    declutter(labels)
    return {"w": W, "h": H, "shapes": shapes, "labels": labels,
            "g0": {"x": X_G0 + NODE + 14, "y": H / 2}, "g2x": X_G2 + NODE + 14}

#!/usr/bin/env python3
"""Regenerate every marketing image from the demo seed, so the site only ever
shows the real app.

    python scripts/marketing_shots.py            # writes static/marketing/*.webp
    python scripts/marketing_shots.py --out DIR  # somewhere else
    python scripts/marketing_shots.py --themes light dark-a  # also NAME-dark.webp, Welcome in dark mode

With several themes, every one is shot from the same seeded demo herd in one run, so their dates match.

It builds a throwaway SQLite database and media folder, runs migrate and
seed_demo, signs in as the demo account with a server-side session (no
password needed), starts runserver on a free port and captures each component
with headless Chromium at 2x. Each image is saved as NAME.webp (2x) and
NAME-1x.webp. Needs the built CSS/JS (npm run build) and Playwright; set
CHROME to a Chrome/Chromium binary if Playwright's own is not installed.
"""
import argparse, json, os, shutil, socket, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable

# name: (path, viewport width, how to frame it). Frames are run in the page by shoot().
SHOTS = [
    ("hero-1280", "/", 1280, {"from": "top", "height": 1136}),
    ("hero-390", "/", 390, {"phone_at": "[data-tiles]", "height": 844}),
    ("tree", "/rabbits/{juniper}/pedigree/?view=family", 1280,
     {"click": ".ft-chip:has-text('ruby-eyed white')", "el": "main", "skip_to": ".ft-genebar", "to": ".ft-stage", "pad": 8}),
    ("weights", "/weights/?view=table", 1280, {"click": "nav[aria-label='Saved views'] a:has-text('Growing out')", "el": "table", "rows": 8}),
    ("litters", "/litters/", 1280, {"el": "[data-group='expecting'], main section", "first": True}),
    ("pairing", "/pairings/{pairing}/", 1280, {"open": "[data-inbreeding] details", "top_of": "h2:has-text('The pair')", "to": "[data-inbreeding]", "pad": 8}),
    ("rabbit", "/rabbits/{photo_rabbit}/", 1280, {"from_el": "main h1", "height": 760}),
    ("offline", "/rabbits/{photo_rabbit}/", 1280, {"open": "[data-add-fold]", "offline": True, "el": "[data-offline-queue='Weight']", "form": "[data-offline-queue='Weight']"}),
]


def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close(); return port


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "static" / "marketing"))
    ap.add_argument("--only", nargs="*", help="shot names to (re)take")
    ap.add_argument("--themes", nargs="+", default=["light"], help="app themes; any but light adds a -dark suffix")
    args = ap.parse_args()
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="bb-shots-"))
    port = free_port()
    env = {**os.environ, "SECRET_KEY": "marketing-shots-only-0123456789abcdefghij", "DEBUG": "1",
           "DATABASE_URL": f"sqlite:///{tmp / 'db.sqlite3'}", "MEDIA_ROOT": str(tmp / "media"), "PHOTO_STORAGE": "",
           "ALLOWED_HOSTS": "localhost,127.0.0.1", "WEBAUTHN_RP_ID": "localhost", "WEBAUTHN_ORIGIN": f"http://localhost:{port}"}
    manage = lambda *a, **kw: subprocess.run([PY, "manage.py", *a], cwd=ROOT, env=env, check=True, **kw)
    server = None
    try:
        manage("migrate", "-v0")
        manage("seed_demo", "--no-password", stdout=subprocess.DEVNULL)
        info = json.loads(manage("shell", "-c", SESSION_CODE, capture_output=True, text=True).stdout.strip().splitlines()[-1])
        server = subprocess.Popen([PY, "manage.py", "runserver", f"127.0.0.1:{port}", "--insecure", "--noreload"],
                                  cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        base = f"http://localhost:{port}"
        for _ in range(60):
            try: urllib.request.urlopen(base + "/login/"); break
            except Exception: time.sleep(0.5)
        for theme in args.themes:
            manage("shell", "-c", THEME_CODE.replace("THEME", repr(theme)), stdout=subprocess.DEVNULL)
            shoot(base, info, out, args.only, "" if theme == "light" else "-dark")
    finally:
        if server: server.terminate()
        shutil.rmtree(tmp, ignore_errors=True)


SESSION_CODE = """
import json
from django.contrib.auth import get_user_model, SESSION_KEY, BACKEND_SESSION_KEY, HASH_SESSION_KEY
from django.contrib.sessions.backends.db import SessionStore
from rabbits.models import Pairing, Rabbit
u = get_user_model().objects.get(email="demo@bramble-burrow.app")
s = SessionStore(); s[SESSION_KEY] = str(u.pk); s[BACKEND_SESSION_KEY] = "django.contrib.auth.backends.ModelBackend"
s[HASH_SESSION_KEY] = u.get_session_auth_hash(); s.create()
r = Rabbit.objects.filter(owner=u)
pair = Pairing.objects.filter(owner=u, doe__name="Nimbus", buck__name="Basalt").first() or Pairing.objects.filter(owner=u).first()
print(json.dumps({"sid": s.session_key, "juniper": r.get(name="Juniper").pk, "pairing": pair.pk,
                  "photo_rabbit": r.get(name="Snow").pk}))
"""


THEME_CODE = """
from django.contrib.auth import get_user_model
get_user_model().objects.filter(email="demo@bramble-burrow.app").update(ui_theme=THEME)
"""


def box(page, sel):
    b = page.locator(sel).first.bounding_box()
    if not b: raise SystemExit(f"not found: {sel}")
    return b


def shoot(base, info, out, only, suffix=""):
    from playwright.sync_api import sync_playwright
    from PIL import Image
    with sync_playwright() as p:
        kw = {"executable_path": os.environ["CHROME"]} if os.environ.get("CHROME") else {}
        browser = p.chromium.launch(**kw)
        for name, path, width, how in SHOTS:
            if only and name not in only: continue
            ctx = browser.new_context(viewport={"width": width, "height": 900 if width > 600 else 844}, device_scale_factor=2,
                                      reduced_motion="reduce", color_scheme="dark" if suffix else "light")
            ctx.add_cookies([{"name": "sessionid", "value": info["sid"], "url": base}])
            page = ctx.new_page()
            page.goto(base + path.format(**info)); page.wait_for_load_state("networkidle")
            page.add_style_tag(content="*{caret-color:transparent!important;transition:none!important;animation:none!important}")
            if how.get("click"): page.locator(how["click"]).first.click(); page.wait_for_timeout(600)
            if how.get("open"): page.evaluate("s => document.querySelectorAll(s).forEach(d => d.open = true)", how["open"])
            if how.get("offline"):
                ctx.set_offline(True); page.wait_for_timeout(300)
                form = page.locator(how["form"]).first
                form.locator("input[name=lb]").fill("9"); form.locator("input[name=oz]").fill("6")
                form.locator("button[type=submit]").first.click(); page.wait_for_timeout(800)
                page.locator("[data-offline-note]").first.wait_for(state="visible")
            page.evaluate("() => scrollTo(0, 0)"); page.wait_for_timeout(100)
            clip = frame(page, how, width)
            name = name + suffix
            png = out / f"{name}.png"
            in_view = clip.pop("viewport", False)
            page.screenshot(path=str(png), clip=clip, full_page=not in_view)
            im = Image.open(png).convert("RGB")
            im.save(out / f"{name}.webp", quality=74, method=6)
            im.resize((im.width // 2, im.height // 2), Image.LANCZOS).save(out / f"{name}-1x.webp", quality=82, method=6)
            png.unlink()
            print(f"{name}: {im.width // 2}x{im.height // 2}")
            ctx.close()
        browser.close()


def frame(page, how, width):
    pad = how.get("pad", 0)
    if how.get("from") == "top":
        h = how.get("height") or (box(page, how["to"])["y"] + box(page, how["to"])["height"] + pad)
        page.set_viewport_size({"width": width, "height": int(h)})
        return {"x": 0, "y": 0, "width": width, "height": int(h)}
    if how.get("from_el"):
        b = box(page, how["from_el"]); main = box(page, "main")
        return {"x": main["x"], "y": b["y"] - 24, "width": main["width"], "height": how["height"]}
    if how.get("skip_to"):
        a, z = box(page, how["skip_to"]), box(page, how["to"])
        return {"x": z["x"] - pad, "y": a["y"] - pad, "width": z["width"] + 2 * pad, "height": z["y"] + z["height"] - a["y"] + 2 * pad}
    if how.get("rows"):
        t = box(page, how["el"]); rows = page.locator(how["el"] + " tbody tr")
        last = rows.nth(min(how["rows"], rows.count()) - 1).bounding_box()
        return {"x": t["x"], "y": t["y"], "width": t["width"], "height": last["y"] + last["height"] - t["y"]}
    if how.get("top_of"):
        a, z = box(page, how["top_of"]), box(page, how["to"])
        col = page.locator(how["top_of"]).first.evaluate("e => { const r = e.parentElement.getBoundingClientRect(); return {x: r.x, width: r.width}; }")
        return {"x": col["x"] - pad, "y": a["y"] - 16, "width": col["width"] + 2 * pad, "height": z["y"] + z["height"] - a["y"] + 16 + pad}
    if how.get("phone_at"):
        y = box(page, how["phone_at"])["y"] - 72  # below the sticky app header
        page.evaluate("y => scrollTo(0, y)", y); page.wait_for_timeout(200)
        return {"x": 0, "y": 0, "width": width, "height": how["height"], "viewport": True}
    b = box(page, how["el"])
    return {"x": b["x"] - 8, "y": b["y"] - 8, "width": b["width"] + 16, "height": b["height"] + 16}


if __name__ == "__main__":
    main()

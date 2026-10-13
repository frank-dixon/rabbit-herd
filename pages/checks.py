"""Startup check: the built CSS must match the source. static/css/app.css is
not in git, so a pull without `npm run build` serves old CSS to new templates
(no theme tokens, broken rows). Shows on runserver, migrate and check."""

from pathlib import Path

from django.conf import settings
from django.core import checks

# Things every page needs from the built CSS; each comes from a different source file.
MARKERS = ("--surface", ".sr-only", "select:not([multiple])", "[data-swipe]")


def css_problems(base=None):
    base = Path(base or settings.BASE_DIR)
    built = base / "static" / "css" / "app.css"
    if not built.exists():
        return ["static/css/app.css is missing. Run npm run build."]
    css = built.read_text(errors="ignore")
    from accounts.models import User

    problems = [f"the built CSS has no {m}" for m in MARKERS if m not in css]
    problems += [f"the built CSS has no {key} theme" for key, _ in User.THEMES if f'data-theme="{key}"' not in css
                 and f"data-theme={key}" not in css]
    sources = [p for p in (base / "assets").glob("*.css")]
    newest = max((p.stat().st_mtime for p in sources), default=0)
    if newest > built.stat().st_mtime + 1:
        problems.append("assets/*.css changed after the last build")
    return problems


@checks.register()
def built_css_is_current(app_configs, **kwargs):
    problems = css_problems()
    if not problems:
        return []
    return [checks.Warning("Built CSS is out of date: " + "; ".join(problems) + ".",
                           hint="Run npm run build, then collectstatic, then restart.", id="pages.W001")]

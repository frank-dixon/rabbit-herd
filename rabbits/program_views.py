"""Breeding programs: a guided setup (Goal, Breeders, Plan) and the program
page with its Flow, Tree and Table views. Every step is a plain form."""

from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from . import program_plan as plan_mod
from .color_odds import SERIES
from .models import Program, ProgramBreeder, Rabbit, Task
from .planner import PLAN_LOCI, read_pattern

COI_CHOICES = [("6.25", "6.25%"), ("12.5", "12.5%"), ("25", "25%")]
VIEWS = [("flow", "Flow"), ("tree", "Tree"), ("table", "Table")]


def owned(request, pk):
    return get_object_or_404(Program, pk=pk, owner=request.user)


def locus_choices(locus):
    """Custom-target options at one locus: shows X, or the bottom recessive pair."""
    series = SERIES[locus]
    if locus == "En":
        return [("Enen", "En en · broken"), ("EnEn", "En En · charlie"), ("enen", "en en · solid")]
    return [(f"{x}_", f"{x}_ · shows {x}") for x in series[:-1]] + [(series[-1] * 2, f"{series[-1]}{series[-1]} · recessive")]


def steps(current, program=None):
    order = [("goal", "Goal", "Target and traits"), ("breeders", "Breeders", "Does, bucks, outside"), ("plan", "Plan", "Generations and odds")]
    reached = ["goal", "breeders", "plan"].index(program.step) if program else 0
    here = ["goal", "breeders", "plan"].index(current)
    return [{"n": i + 1, "key": k, "label": l, "help": h, "current": k == current, "done": i < here or i < reached}
            for i, (k, l, h) in enumerate(order)]


@login_required
def program_list(request):
    programs = list(Program.objects.filter(owner=request.user))
    return render(request, "programs/list.html", {"programs": programs, "wide": True})


def goal_values(program):
    if program is None:
        return {"name": "", "target_key": "broken-black", "traits": "", "keep_count": 2, "keep_sex": "doe", "max_coi": "12.5",
                "custom": {}}
    return {"name": program.name, "target_key": program.target_key or "custom", "traits": ", ".join(program.traits),
            "keep_count": program.keep_count, "keep_sex": program.keep_sex, "max_coi": f"{program.max_coi.normalize():f}",
            "custom": program.target if not program.target_key else {}}


def read_goal(post):
    """(values, errors, cleaned) from the goal form."""
    values = {"name": post.get("name", "").strip()[:80], "target_key": post.get("target_key", ""),
              "traits": post.get("traits", "").strip(), "keep_count": post.get("keep_count", "2"),
              "keep_sex": post.get("keep_sex", "doe"), "max_coi": post.get("max_coi", "12.5"),
              "custom": {locus: post.get(f"custom_{locus}", "") for locus in PLAN_LOCI if post.get(f"custom_{locus}")}}
    errors = {}
    if values["target_key"] in plan_mod.TARGET_KEYS:
        label, _, target = plan_mod.TARGET_KEYS[values["target_key"]]
    elif values["target_key"] == "custom":
        target = {locus: pattern for locus, pattern in values["custom"].items()
                  if pattern in dict(locus_choices(locus)) and read_pattern(locus, pattern)}
        label = values["name"] or "Custom color"
        if not target:
            errors["target"] = "Choose at least one gene for the custom color."
    else:
        label, target = "", {}
        errors["target"] = "Choose a target color."
    try:
        keep = int(values["keep_count"])
        if not 1 <= keep <= 20:
            raise ValueError
    except ValueError:
        keep = 2
        errors["keep_count"] = "Keep between 1 and 20."
    if values["keep_sex"] not in Program.KeepSex.values:
        errors["keep_sex"] = "Choose does, bucks or either."
    if values["max_coi"] not in dict(COI_CHOICES):
        errors["max_coi"] = "Choose a COI limit."
    traits = [t.strip()[:40] for t in values["traits"].split(",") if t.strip()][:8]
    cleaned = {"name": values["name"], "target_key": values["target_key"] if values["target_key"] != "custom" else "",
               "target_label": label, "target": target, "traits": traits, "keep_count": keep,
               "keep_sex": values["keep_sex"], "max_coi": Decimal(values["max_coi"]) if not errors.get("max_coi") else Decimal("12.5")}
    return values, errors, cleaned


def goal_page(request, program):
    values = goal_values(program)
    errors = {}
    if request.method == "POST":
        values, errors, cleaned = read_goal(request.POST)
        if not errors:
            if program is None:
                program = Program(owner=request.user)
            for field, value in cleaned.items():
                setattr(program, field, value)
            if program.step == Program.Step.GOAL:
                program.step = Program.Step.BREEDERS
            program.save()
            return redirect("program_breeders", program.pk)
    custom_rows = [{"locus": locus, "name": f"custom_{locus}", "options": locus_choices(locus),
                    "value": values["custom"].get(locus, "")} for locus in PLAN_LOCI]
    targets = [{"key": k, "label": l, "text": t, "genes": plan_mod.target_text(g)} for k, l, t, g in plan_mod.TARGETS]
    return render(request, "programs/setup.html", {
        "program": program, "steps": steps("goal", program), "stage": "goal", "values": values, "errors": errors,
        "targets": targets, "custom_rows": custom_rows, "coi_choices": COI_CHOICES,
        "keep_sex_choices": Program.KeepSex.choices, "wide": True,
    })


@login_required
def program_new(request):
    return goal_page(request, None)


@login_required
def program_goal(request, pk):
    return goal_page(request, owned(request, pk))


@login_required
def program_breeders(request, pk):
    program = owned(request, pk)
    if not program.target:
        return redirect("program_goal", program.pk)
    breeders = plan_mod.candidates(program)
    ped = plan_mod.pedigree(request.user)
    rows = plan_mod.ranked_pairings(program, breeders, ped)
    current = f"h:{program.dam_id}|{plan_mod.sire_key(program)}" if program.dam_id else ""
    error = ""
    if request.method == "POST":
        choice = request.POST.get("pairing", "")
        row = next((r for r in rows if r["value"] == choice), None)
        if row is None:
            error = "Choose a starting pairing."
        else:
            program.dam = row["doe"]["rabbit"]
            buck = row["buck"]
            program.sire = buck["rabbit"]
            program.sire_outside = buck.get("breeder")
            program.g2_sire = program.g2_outside = None  # the plan picks the best mate again
            program.step = Program.Step.PLAN
            if not program.name:
                program.name = f"{program.target_label} from {row['doe']['name']}’s line"[:80]
            program.save()
            return redirect("program_detail", program.pk)
    show_all = request.GET.get("all") == "1"
    shown = rows if show_all else rows[:6]
    if current and not any(r["value"] == current for r in shown):
        shown += [r for r in rows if r["value"] == current]
    selected = current or (rows[0]["value"] if rows else "")
    odds_by = best_odds(rows)
    return render(request, "programs/setup.html", {
        "program": program, "steps": steps("breeders", program), "stage": "breeders", "rows": shown,
        "total": len(rows), "show_all": show_all, "selected": selected, "error": error,
        "breeders": breeder_cards(program, breeders, odds_by, picked=set(selected.split("|")) if selected else set()),
        "target_text": plan_mod.target_text(program.target), "wide": True,
    })


def best_odds(rows):
    """{breeder key: the best odds line it has in any pairing}."""
    best = {}
    for r in rows:
        for me, other in ((r["doe"], r["buck"]), (r["buck"], r["doe"])):
            if me["key"] not in best or r["high"] > best[me["key"]][0]:
                best[me["key"]] = (r["high"], f"{r['odds']} with {other['name']}" if r["high"] else "")
    return best


def breeder_cards(program, breeders, odds_by, picked):
    cards = []
    for b in breeders:
        if b["sex"] == "doe" and b["outside"]:
            continue
        line = odds_by.get(b["key"], (0, ""))[1] or (f"0%, no {target_gene_word(program)}" if program.target.get("En") == "Enen" and "En" not in b["genes"].get("En", ()) else "0% with any mate here")
        cards.append({**b, "picked": b["key"] in picked, "genes_text": plan_mod.pairs_text(b["genes"], program.target) if any(set(pair) != {"_"} for pair in b["genes"].values()) else "Genes not recorded",
                      "odds_line": line})
    cards.sort(key=lambda c: (not c["picked"], c["sex"] != "doe", c["sold"], c["outside"], c["name"]))
    return cards


def target_gene_word(program):
    return "En"


@login_required
def program_detail(request, pk):
    program = owned(request, pk)
    if program.step != Program.Step.PLAN:
        return redirect("program_goal" if program.step == Program.Step.GOAL else "program_breeders", program.pk)
    # Phones (the "narrow" cookie, set by the page) open on Tree: Flow needs width.
    default = "tree" if request.COOKIES.get("narrow") == "1" else "flow"
    view = request.GET.get("view", default)
    if view not in dict(VIEWS):
        view = default
    plan = plan_mod.build(program)
    if plan.get("missing"):
        messages.error(request, "A breeder in this plan is no longer in your records. Pick the starting pairing again.")
        return redirect("program_breeders", program.pk)
    from .program_flow import flow_svg

    odds_by = best_odds(plan_mod.ranked_pairings(program, plan["breeders"], plan_mod.pedigree(request.user)))
    picked = set(plan["picked"]) | ({plan["g2"]["mate"]["key"]} if plan.get("g2") else set())
    return render(request, "programs/detail.html", {
        "program": program, "plan": plan, "view": view, "flow": flow_svg(plan, program) if view == "flow" else None,
        "view_options": [{"href": f"?view={k}", "label": l, "selected": k == view} for k, l in VIEWS],
        "breeders": breeder_cards(program, plan["breeders"], odds_by, picked), "wide": True,
    })


@login_required
def program_g2(request, pk):
    """Swap the mate for the kept G1 kit."""
    program = owned(request, pk)
    plan = plan_mod.build(program)
    if plan.get("missing"):
        return redirect("program_breeders", program.pk)
    options = plan["options"]
    if request.method == "POST":
        key = request.POST.get("mate", "")
        chosen = next((o["mate"] for o in options if o["mate"]["key"] == key), None)
        if chosen:
            program.g2_sire = chosen["rabbit"]
            program.g2_outside = chosen.get("breeder")
            program.save(update_fields=["g2_sire", "g2_outside"])
            messages.success(request, f"G2 now pairs the kept {plan['kit_word']} with {chosen['name']}.")
            return redirect("program_detail", program.pk)
        messages.error(request, "Choose a mate.")
    rows = [{**o, "odds_text": plan_mod.P.percent_text(o["odds"], 0), "coi_text": plan_mod.P.percent_text(o["coi"]),
             "genes_text": plan_mod.pairs_text(o["mate"]["genes"], program.target)} for o in options]
    return render(request, "programs/g2.html", {"program": program, "plan": plan, "rows": rows,
                                                "current": plan["g2"]["mate"]["key"] if plan.get("g2") else ""})


@login_required
def program_outside(request, pk):
    """Add an outside breeder with the genes its owner gave. No fees: the
    planner only weighs genes, odds and inbreeding."""
    program = owned(request, pk)
    back = request.GET.get("next") or request.POST.get("next") or reverse("program_breeders", args=[program.pk])
    if not back.startswith("/programs/"):
        back = reverse("program_breeders", args=[program.pk])
    values = {"name": "", "sex": "buck", "breed": "", "rabbitry": "", **{f"gene_{l}": "" for l in PLAN_LOCI}}
    errors = {}
    if request.method == "POST":
        values = {k: request.POST.get(k, "").strip() for k in values}
        if not values["name"]:
            errors["name"] = "Give the outside rabbit a name."
        if values["sex"] not in ("doe", "buck"):
            errors["sex"] = "Choose doe or buck."
        genes = {}
        for locus in PLAN_LOCI:
            text = values[f"gene_{locus}"]
            if text:
                from .color_odds import parse

                if parse(locus, text) is None:
                    errors[f"gene_{locus}"] = f"Write {locus} like {locus_choices(locus)[0][0].replace('_', '/_')}."
                else:
                    genes[locus] = text
        if not errors:
            ProgramBreeder.objects.create(program=program, name=values["name"][:120], sex=values["sex"],
                                          breed=values["breed"][:80], rabbitry=values["rabbitry"][:120], genes=genes)
            messages.success(request, f"{values['name']} was added to this program’s breeders.")
            return redirect(back)
    gene_rows = [{"locus": l, "name": f"gene_{l}", "value": values[f"gene_{l}"], "error": errors.get(f"gene_{l}", ""),
                  "hint": {"A": "A/a, at/a or a/a", "B": "B/b", "C": "C/c", "D": "D/d", "E": "E/e", "En": "En/en"}[l]}
                 for l in PLAN_LOCI]
    return render(request, "programs/outside.html", {"program": program, "values": values, "errors": errors,
                                                     "gene_rows": gene_rows, "back": back, "sexes": [("buck", "Buck"), ("doe", "Doe")]})


@login_required
@require_POST
def program_schedule(request, pk):
    """Put the G2 breeding on Tasks for its planned day."""
    program = owned(request, pk)
    plan = plan_mod.build(program)
    g2 = plan.get("g2")
    if not g2:
        return redirect("program_detail", program.pk)
    if program.g2_task_id and program.g2_task.done_at is None:
        messages.success(request, "G2 is already on your tasks.")
        return redirect("program_detail", program.pk)
    task = Task.objects.create(owner=request.user, title=f"Breed the kept G1 {plan['kit_word']} to {g2['mate']['name']} ({program.title})"[:120],
                               due_on=g2["start"], rabbit=program.dam)
    program.g2_task = task
    program.save(update_fields=["g2_task"])
    messages.success(request, f"Added to your tasks for {plan_mod.nice_date(g2['start'])}.")
    return redirect("program_detail", program.pk)


@login_required
@require_POST
def program_delete(request, pk):
    program = owned(request, pk)
    title = program.title
    program.delete()
    messages.success(request, f"{title} was deleted.")
    return redirect("program_list")

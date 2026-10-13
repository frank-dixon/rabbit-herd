/*
 * Helpers for the add-a-rabbit card flow (rabbits/flow_views.py).
 *
 * The flow works without this file: every card is a normal form, and the
 * server checks every answer. This only makes it nicer:
 * - the crossbred total updates as shares are typed;
 * - once a row is the dam (or sire), the other rows stop offering it, and
 *   it comes back when that row changes or is removed;
 * - typing is saved to the draft as it happens, so a refresh keeps it;
 * - focus moves to the error summary, the row just added, or the question;
 * - "Start over" asks before clearing the draft.
 * The wording and rules match the server's. Change both together.
 */

const TOTAL_BASE = "rounded px-3 py-2 text-sm font-semibold ";
const TOTAL_TONES = {
  good: "bg-green-100 text-green-900",
  over: "bg-red-100 text-red-900",
  short: "bg-neutral-100 text-neutral-800",
};
const PARENTS = ["dam", "sire"];
const AUTOSAVE_DELAY_MS = 600;

/**
 * Sum the shares, counting only plain numbers, like the server does. Adds in
 * hundredths so 75 + 12.5 + 12.5 is exactly 100 (no float drift).
 */
export function crossTotal(values) {
  const hundredths = values.reduce(function (sum, value) {
    const text = String(value).trim();
    return /^-?\d+(\.\d+)?$/.test(text) ? sum + Math.round(Number(text) * 100) : sum;
  }, 0);
  return hundredths / 100;
}

/** 12.5 -> "12.5", 50 -> "50", 33.333 -> "33.33". */
export function shareText(value) {
  return String(Math.round(value * 100) / 100);
}

export function totalText(total) {
  if (total === 100) {
    return "Total: 100%. The mix adds up.";
  }
  if (total < 100) {
    return "Total so far: " + shareText(total) + "%. Add " + shareText(100 - total) + "% more to reach 100%.";
  }
  return "Total so far: " + shareText(total) + "%. That's " + shareText(total - 100) + "% over, so lower a share.";
}

export function totalTone(total) {
  if (total === 100) {
    return "good";
  }
  return total > 100 ? "over" : "short";
}

/**
 * Relationship choices for row `index`, given every row's current value.
 * The first row to take Dam or Sire keeps it; other rows lose it. A row
 * always keeps its own value, and the server still rejects a second one.
 */
export function relationshipChoices(all, values, index) {
  const takenBy = {};
  values.forEach(function (value, rowIndex) {
    if (PARENTS.includes(value) && !(value in takenBy)) {
      takenBy[value] = rowIndex;
    }
  });
  const own = values[index];
  return all.filter(function (choice) {
    const owner = takenBy[choice[0]];
    return owner === undefined || owner === index || choice[0] === own;
  });
}

function bindTotal(form) {
  const fieldset = form.querySelector("[data-cross]");
  const output = form.querySelector("[data-cross-total]");
  if (!fieldset || !output) {
    return;
  }
  fieldset.addEventListener("input", function () {
    const values = Array.from(fieldset.querySelectorAll('[data-role="share"]')).map(function (input) {
      return input.value;
    });
    const total = crossTotal(values);
    output.textContent = totalText(total);
    output.className = TOTAL_BASE + TOTAL_TONES[totalTone(total)];
  });
}

function bindRelationships(form) {
  const source = document.getElementById("relationship-choices");
  const selects = Array.from(form.querySelectorAll('select[data-role="relationship"]'));
  if (!source || !selects.length) {
    return;
  }
  const all = JSON.parse(source.textContent);
  function refresh() {
    const values = selects.map(function (select) {
      return select.value;
    });
    selects.forEach(function (select, index) {
      const allowed = relationshipChoices(all, values, index);
      const placeholder = select.options[0];
      const current = select.value;
      // Rebuild rather than hide: Safari on iPhone ignores hidden options.
      select.replaceChildren(placeholder);
      allowed.forEach(function (choice) {
        const option = new Option(choice[1], choice[0], false, choice[0] === current);
        select.add(option);
      });
      select.value = current;
    });
  }
  selects.forEach(function (select) {
    select.addEventListener("change", refresh);
  });
  refresh();
}

/** Whether the color card's description box is needed for a choice. */
export function needsColorText(choice, other) {
  return choice === other;
}

/** Show the description box only once Another color is chosen. Without
 * JavaScript the box simply stays visible. */
function bindColorChoice(form) {
  const box = form.querySelector("[data-color-other]");
  if (!box) {
    return;
  }
  const other = box.getAttribute("data-color-other");
  function current() {
    const checked = form.querySelector('input[name="color_choice"]:checked');
    const select = form.querySelector('select[name="color_choice"]');
    return checked ? checked.value : select ? select.value : "";
  }
  function update(event) {
    const show = needsColorText(current(), other);
    box.hidden = !show;
    if (show && event && event.target && event.target.name === "color_choice") {
      const input = box.querySelector("input");
      if (input) {
        input.focus();
      }
    }
  }
  form.addEventListener("change", function (event) {
    if (event.target && event.target.name === "color_choice") {
      update(event);
    }
  });
  update();
}

function bindAutosave(form) {
  let timer = null;
  function save() {
    timer = null;
    const data = new FormData(form);
    data.set("action", "save");
    // form.action would return the buttons named "action", so read the attribute.
    fetch(form.getAttribute("action"), {
      method: "POST",
      body: data,
      credentials: "same-origin",
      headers: { "X-Autosave": "1" },
    }).catch(function () {
      /* Next and Back still post everything, so a missed save is harmless. */
    });
  }
  function schedule() {
    if (timer) {
      clearTimeout(timer);
    }
    timer = setTimeout(save, AUTOSAVE_DELAY_MS);
  }
  form.addEventListener("input", schedule);
  form.addEventListener("change", schedule);
  form.addEventListener("submit", function () {
    if (timer) {
      clearTimeout(timer);
      timer = null;
    }
  });
}

function bindConfirm(root) {
  root.querySelectorAll("form[data-confirm]").forEach(function (form) {
    form.addEventListener("submit", function (event) {
      if (!window.confirm(form.getAttribute("data-confirm"))) {
        event.preventDefault();
      }
    });
  });
}

export function parseAuto(text) {
  const out = {};
  String(text || "").split(";").forEach(function (part) {
    const at = part.indexOf("=");
    if (at > 0) {
      out[part.slice(0, at)] = part.slice(at + 1);
    }
  });
  return out;
}

export function autoText(auto, loci) {
  return loci.filter(function (locus) { return locus in auto; }).map(function (locus) {
    return locus + "=" + auto[locus];
  }).join(";");
}

/**
 * The same rule as flow.fill_genes on the server: fill a locus that is
 * empty or still holds the value filled before; leave the rest alone.
 * Returns { values, auto }.
 */
export function refillGenes(values, auto, suggestions) {
  const nextValues = Object.assign({}, values);
  const nextAuto = {};
  Object.keys(values).forEach(function (locus) {
    const current = (values[locus] || "").trim();
    const stillAuto = locus in auto && current === auto[locus];
    if (current && !stillAuto) {
      return;
    }
    if (suggestions[locus]) {
      nextValues[locus] = suggestions[locus];
      nextAuto[locus] = suggestions[locus];
    } else if (stillAuto) {
      nextValues[locus] = "";
    }
  });
  return { values: nextValues, auto: nextAuto };
}

/** Live fill on the genes card when the eye color changes. */
function bindGeneFill(form) {
  const data = document.getElementById("gene-suggestions");
  const hidden = form.querySelector("[data-gene-auto]");
  const eye = form.querySelector("#id_eye_color");
  if (!data || !hidden || !eye) {
    return;
  }
  const byEye = JSON.parse(data.textContent);
  const fields = Array.from(form.querySelectorAll("[data-gene]"));
  const loci = fields.map(function (field) { return field.getAttribute("data-gene"); });
  const refill = form.querySelector("[data-gene-refill]");
  if (refill) {
    refill.hidden = true;
  }
  function show(auto) {
    fields.forEach(function (field) {
      const hint = field.parentElement.querySelector("[data-gene-filled]");
      if (hint) {
        hint.classList.toggle("hidden", !(field.getAttribute("data-gene") in auto));
      }
    });
  }
  eye.addEventListener("change", function () {
    const values = {};
    fields.forEach(function (field) { values[field.getAttribute("data-gene")] = field.value; });
    const result = refillGenes(values, parseAuto(hidden.value), byEye[eye.value] || {});
    fields.forEach(function (field) {
      const value = result.values[field.getAttribute("data-gene")];
      if (field.tagName === "SELECT" && value && !Array.from(field.options).some(function (o) { return o.value === value; })) {
        return;
      }
      field.value = value;
    });
    hidden.value = autoText(result.auto, loci);
    show(result.auto);
  });
  form.addEventListener("change", function (event) {
    const locus = event.target.getAttribute && event.target.getAttribute("data-gene");
    if (!locus) {
      return;
    }
    const auto = parseAuto(hidden.value);
    if (locus in auto && auto[locus] !== event.target.value) {
      delete auto[locus];
      hidden.value = autoText(auto, loci);
      show(auto);
    }
  });
}

/** Errors first, then a row that was just added, then the question. */
function placeFocus(form) {
  const summary = document.getElementById("error-summary");
  if (summary) {
    summary.focus();
    return;
  }
  const hash = window.location.hash.slice(1);
  const target = hash ? document.getElementById(hash) : null;
  if (target) {
    target.focus();
    return;
  }
  const question = document.getElementById("question");
  if (question && form.getAttribute("data-step") !== "name") {
    question.focus();
  }
}

export function bindRabbitFlow(root) {
  const scope = root || document;
  bindConfirm(scope);
  const form = scope.querySelector("form[data-rabbit-flow]");
  if (!form) {
    return;
  }
  bindTotal(form);
  bindRelationships(form);
  bindColorChoice(form);
  bindGeneFill(form);
  bindAutosave(form);
  placeFocus(form);
}

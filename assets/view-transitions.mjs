/*
 * View transitions are decoration. When the browser skips or aborts one (a fast second navigation, a
 * page that stops opting in mid-load), its promises reject; unhandled, that showed up as a console
 * "Transition was aborted because of invalid state" page error (Critic v3). quiet() marks a
 * transition's promises handled; bindQuietTransitions does it for page-to-page transitions too.
 */
const noop = () => {};

export function quiet(transition) {
  if (!transition) return transition;
  for (const key of ["ready", "finished", "updateCallbackDone"]) transition[key]?.catch?.(noop);
  return transition;
}

/** Start a same-document transition with its promises handled. Returns the transition. */
export function startQuiet(doc, update) {
  return quiet(doc.startViewTransition(update));
}

export function bindQuietTransitions(win) {
  win.addEventListener("pageswap", (event) => quiet(event.viewTransition));
  win.addEventListener("pagereveal", (event) => quiet(event.viewTransition));
}

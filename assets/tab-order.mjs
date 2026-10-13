/*
 * Pure rules for the customizable tab bar, shared by tab-edit.mjs and its tests.
 * Tabs are a list of page keys, 3 to 5 long.
 */
export const MIN = 3;
export const MAX = 5;

/**
 * Put `key` at insertion point `index` (0..tabs.length). A tab already in the
 * bar moves there. A new page is inserted while there is room; once the bar
 * is full it swaps with the tab at that spot instead.
 */
export function insertAt(tabs, key, index, max = MAX) {
  const at = Math.max(0, Math.min(index, tabs.length));
  const from = tabs.indexOf(key);
  if (from !== -1) {
    const next = tabs.filter((k) => k !== key);
    next.splice(from < at ? at - 1 : at, 0, key);
    return next;
  }
  if (tabs.length < max) {
    const next = [...tabs];
    next.splice(at, 0, key);
    return next;
  }
  const next = [...tabs];
  next[Math.min(at, tabs.length - 1)] = key;
  return next;
}

/** Tap-to-add: fill the next empty slot, or null when the bar is full. */
export function addNext(tabs, key, max = MAX) {
  if (tabs.includes(key) || tabs.length >= max) return null;
  return [...tabs, key];
}

/** Remove a tab, or null when that would leave fewer than MIN. */
export function removeTab(tabs, key, min = MIN) {
  if (tabs.length <= min || !tabs.includes(key)) return null;
  return tabs.filter((k) => k !== key);
}

/** The insertion point for a pointer at x, given each slot's [left, right]. */
export function insertionIndex(x, rects) {
  for (let i = 0; i < rects.length; i += 1) {
    if (x < (rects[i][0] + rects[i][1]) / 2) return i;
  }
  return rects.length;
}

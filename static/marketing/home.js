/* Welcome has no app bundle, so it marks its own page-to-page transition promises handled, like
   assets/view-transitions.mjs does in the app: an aborted transition (a fast form post to the demo or
   a guest herd) is decoration, not a console page error. Plain file: no build step, and the
   Content-Security-Policy forbids inline scripts. */
(function () {
  var noop = function () {};
  function quiet(t) {
    if (!t) return;
    ["ready", "finished", "updateCallbackDone"].forEach(function (k) { if (t[k] && t[k].catch) t[k].catch(noop); });
  }
  window.addEventListener("pageswap", function (e) { quiet(e.viewTransition); });
  window.addEventListener("pagereveal", function (e) { quiet(e.viewTransition); });
})();

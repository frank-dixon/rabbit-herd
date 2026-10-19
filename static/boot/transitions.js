/* Page-to-page view transitions are decoration: an aborted one (a fast form post, like Welcome's demo
   or guest herd) must not be a console page error. pagereveal fires before the deferred app bundle
   runs, so this is a plain blocking file in <head> of every page and of Welcome (no app bundle there),
   marking the transition's promises handled the way assets/view-transitions.mjs does. A file, not an
   inline script, so the Content-Security-Policy can forbid inline scripts. */
(function () {
  var noop = function () {};
  function quiet(t) {
    if (!t) return;
    ["ready", "finished", "updateCallbackDone"].forEach(function (k) { if (t[k] && t[k].catch) t[k].catch(noop); });
  }
  window.addEventListener("pageswap", function (e) { quiet(e.viewTransition); });
  window.addEventListener("pagereveal", function (e) { quiet(e.viewTransition); });
})();

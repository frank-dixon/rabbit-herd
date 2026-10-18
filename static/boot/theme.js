/* Guests keep appearance in localStorage so it survives offline and guest cleanup.
   Loaded in <head> (not deferred) so it applies before paint. A file, not an
   inline script, so the Content-Security-Policy can forbid inline scripts. */
(function () {
  var h = document.documentElement;
  if (h.getAttribute("data-guest") !== "1") return;
  try {
    var t = localStorage.getItem("bb-ui-theme");
    if (t) h.setAttribute("data-theme", t);
    var d = localStorage.getItem("bb-ui-density");
    if (d) h.setAttribute("data-density", d);
  } catch (e) {}
})();

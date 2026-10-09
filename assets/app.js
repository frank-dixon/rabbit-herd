/*
 * Front-end entry point.
 *
 * The watch and production scripts minify this file. Comments stay in
 * source so the ceremony code is readable, and they are stripped from
 * the file the browser actually downloads.
 */

/**
 * Read the CSRF token from the page.
 *
 * The CSRF cookie is HttpOnly, so script cannot see it on document.cookie.
 * The base template prints the token into a meta tag instead, and every
 * fetch that changes server state sends it back as X-CSRFToken.
 */
function csrfToken() {
  const meta = document.querySelector('meta[name="csrf-token"]');
  if (!meta) {
    return "";
  }
  return meta.getAttribute("content") || "";
}

window.rabbitHerd = {
  csrfToken,
};

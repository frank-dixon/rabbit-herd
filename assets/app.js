/*
 * Front-end entry point.
 *
 * The watch and production scripts minify this file. Comments stay in
 * source so the ceremony code is readable, and they are stripped from
 * the file the browser actually downloads.
 *
 * Passkeys are created and checked in the browser, then posted to Django
 * for verification. The server decides the relying party, the challenge,
 * and whether the account exists. This file only translates bytes.
 *
 * The add-a-rabbit card flow's helpers live in rabbit-flow.mjs.
 */

import { bindRabbitFlow } from "./rabbit-flow.mjs";
import { bindPhotoUpload } from "./photo-upload.mjs";
import { bindPhotoStep } from "./photo-step.mjs";
import { bindDeleteDialog } from "./delete-dialog.mjs";
import { bindPhotoTiles } from "./photo-tiles.mjs";
import { bindDeathFields } from "./death-fields.mjs";
import { bindOffline } from "./offline.mjs";
import { bindSettings } from "./settings.mjs";
import { bindSettingsSave } from "./settings-save.mjs";
import { bindPairingCheck } from "./pairing-check.mjs";
import { bindConfirmDelete } from "./confirm-delete.mjs";
import { bindFilters } from "./filters.mjs";
import { bindMenu } from "./menu.mjs";
import { bindQuickDone } from "./quick-done.mjs";
import { bindTabEdit } from "./tab-edit.mjs";
import { bindToasts } from "./toast.mjs";
import { bindUndoRemove } from "./undo-remove.mjs";
import { bindSwipe } from "./swipe.mjs";
import { bindWeighIn } from "./weigh-in.mjs";
import { bindPullRefresh } from "./ptr.mjs";
import { bindRepeatFields } from "./repeat-fields.mjs";
import { bindPressReset } from "./press-reset.mjs";
import { bindAccountMenu } from "./account-menu.mjs";
import { bindPrefetch } from "./prefetch.mjs";
import { bindScrollSpy } from "./scrollspy.mjs";
import { bindRabbitInline } from "./rabbit-inline.mjs";
import { bindGuide } from "./guide.mjs";
import { bindSegmented } from "./segmented.mjs";
import { bindFamilyTree } from "./family-tree.mjs";
import { bindListSwap } from "./list-swap.mjs";
import { bindWeightsPage } from "./weights-page.mjs";
import { bindAuthForms } from "./auth-form.mjs";
import { bindLitterPhotos } from "./litter-photos.mjs";
import { bindAddSheets, bindMoreMenus } from "./add-sheet.mjs";
import { bindModal } from "./modal.mjs";
import { bindSideMenu } from "./side-menu.mjs";
import { focusSmooth, reducedMotion } from "./motion.mjs";

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

/**
 * WebAuthn wants ArrayBuffers. Django's library sends those bytes as
 * base64url text so they survive JSON. Put the padding back, then decode.
 */
function base64urlToBuffer(value) {
  const text = String(value).replace(/-/g, "+").replace(/_/g, "/");
  const padded = text + "=".repeat((4 - (text.length % 4)) % 4);
  const binary = atob(padded);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return bytes.buffer;
}

/**
 * The authenticator returns ArrayBuffers. The server expects the same
 * base64url alphabet it used for the challenge, without padding.
 */
function bufferToBase64url(buffer) {
  const bytes = new Uint8Array(buffer);
  let binary = "";
  for (let index = 0; index < bytes.length; index += 1) {
    binary += String.fromCharCode(bytes[index]);
  }
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

function showPasskeyError(message) {
  const element = document.querySelector("[data-passkey-error]");
  if (!element) {
    return;
  }
  element.hidden = false;
  element.textContent = message;
}

async function postJson(url, body) {
  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": csrfToken(),
    },
    body: JSON.stringify(body),
  });
  const data = await response.json().catch(function () {
    return {};
  });
  if (!response.ok) {
    throw new Error(data.error || "The passkey request failed.");
  }
  return data;
}

/**
 * Only follow a path on this site. A passkey response must not be able to
 * send the browser to another origin, even if the JSON is unexpected.
 */
function followRedirect(url) {
  if (typeof url === "string" && url.startsWith("/") && !url.startsWith("//")) {
    window.location.assign(url);
    return;
  }
  window.location.assign("/");
}

function publicKeyCreationOptions(options) {
  const publicKey = Object.assign({}, options, {
    challenge: base64urlToBuffer(options.challenge),
    user: Object.assign({}, options.user, {
      id: base64urlToBuffer(options.user.id),
    }),
  });
  if (Array.isArray(options.excludeCredentials)) {
    publicKey.excludeCredentials = options.excludeCredentials.map(function (item) {
      return Object.assign({}, item, { id: base64urlToBuffer(item.id) });
    });
  }
  return publicKey;
}

function publicKeyRequestOptions(options) {
  const publicKey = Object.assign({}, options, {
    challenge: base64urlToBuffer(options.challenge),
  });
  if (Array.isArray(options.allowCredentials)) {
    publicKey.allowCredentials = options.allowCredentials.map(function (item) {
      return Object.assign({}, item, { id: base64urlToBuffer(item.id) });
    });
  }
  return publicKey;
}

/**
 * Registration and authentication return different response fields.
 * Copy only the buffers the server knows how to verify.
 */
function credentialToJSON(credential) {
  const response = {
    clientDataJSON: bufferToBase64url(credential.response.clientDataJSON),
  };
  if (credential.response.attestationObject) {
    response.attestationObject = bufferToBase64url(credential.response.attestationObject);
    if (typeof credential.response.getTransports === "function") {
      response.transports = credential.response.getTransports();
    }
  } else {
    response.authenticatorData = bufferToBase64url(credential.response.authenticatorData);
    response.signature = bufferToBase64url(credential.response.signature);
    if (credential.response.userHandle) {
      response.userHandle = bufferToBase64url(credential.response.userHandle);
    }
  }
  return {
    id: credential.id,
    rawId: bufferToBase64url(credential.rawId),
    type: credential.type,
    authenticatorAttachment: credential.authenticatorAttachment,
    clientExtensionResults: credential.getClientExtensionResults(),
    response: response,
  };
}

async function registerPasskey(button) {
  if (!window.PublicKeyCredential) {
    showPasskeyError("This browser does not support passkeys.");
    return;
  }
  const body = {};
  const emailFieldId = button.getAttribute("data-email-field");
  if (emailFieldId) {
    const emailField = document.getElementById(emailFieldId);
    const email = emailField ? emailField.value.trim() : "";
    if (!email) {
      showPasskeyError("Enter an email address first.");
      return;
    }
    body.email = email;
  }
  const options = await postJson("/accounts/passkey/register/options/", body);
  const credential = await navigator.credentials.create({
    publicKey: publicKeyCreationOptions(options),
  });
  const result = await postJson("/accounts/passkey/register/verify/", {
    credential: credentialToJSON(credential),
  });
  followRedirect(result.redirect);
}

/**
 * Autofill and the button each store a challenge in the session. Only the
 * latest one can be verified, so a newer attempt cancels the older one.
 */
let passkeyCeremony = 0;
let conditionalAbort = null;

function beginPasskeyCeremony() {
  passkeyCeremony += 1;
  if (conditionalAbort) {
    conditionalAbort.abort();
    conditionalAbort = null;
  }
  return passkeyCeremony;
}

async function signInWithPasskey(button) {
  if (!window.PublicKeyCredential) {
    showPasskeyError("This browser does not support passkeys.");
    return;
  }
  const ceremony = beginPasskeyCeremony();
  const options = await postJson("/accounts/passkey/login/options/", {});
  if (ceremony !== passkeyCeremony) {
    return;
  }
  const credential = await navigator.credentials.get({
    publicKey: publicKeyRequestOptions(options),
  });
  if (ceremony !== passkeyCeremony) {
    return;
  }
  const result = await postJson("/accounts/passkey/login/verify/", {
    credential: credentialToJSON(credential),
    next: button.getAttribute("data-next") || "",
  });
  followRedirect(result.redirect);
}

/**
 * Conditional mediation is the passkey row in the email field's autofill,
 * not a modal. It can start with the page. AbortError means the button
 * took over, and a dismissed sheet is not a failed sign-in.
 */
async function offerPasskeyAutofill(button) {
  if (
    !window.PublicKeyCredential ||
    typeof PublicKeyCredential.isConditionalMediationAvailable !== "function"
  ) {
    return;
  }
  let available = false;
  try {
    available = await PublicKeyCredential.isConditionalMediationAvailable();
  } catch (error) {
    return;
  }
  if (!available || passkeyCeremony !== 0) {
    return;
  }
  const ceremony = beginPasskeyCeremony();
  const controller = new AbortController();
  conditionalAbort = controller;
  let credential = null;
  try {
    const options = await postJson("/accounts/passkey/login/options/", {});
    if (ceremony !== passkeyCeremony || controller.signal.aborted) {
      return;
    }
    credential = await navigator.credentials.get({
      mediation: "conditional",
      signal: controller.signal,
      publicKey: publicKeyRequestOptions(options),
    });
  } catch (error) {
    return;
  }
  if (ceremony !== passkeyCeremony || !credential) {
    return;
  }
  const result = await postJson("/accounts/passkey/login/verify/", {
    credential: credentialToJSON(credential),
    next: button.getAttribute("data-next") || "",
  });
  followRedirect(result.redirect);
}

function bindPasskeys() {
  const registerButton = document.getElementById("passkey-register");
  if (registerButton) {
    registerButton.addEventListener("click", function () {
      registerPasskey(registerButton).catch(function (error) {
        showPasskeyError(error.message || "The passkey could not be created.");
      });
    });
  }
  const loginButton = document.getElementById("passkey-login");
  if (loginButton) {
    loginButton.addEventListener("click", function () {
      signInWithPasskey(loginButton).catch(function (error) {
        showPasskeyError(error.message || "The passkey could not be used.");
      });
    });
    offerPasskeyAutofill(loginButton).catch(function (error) {
      showPasskeyError(error.message || "The passkey could not be used.");
    });
  }
}

window.rabbitHerd = {
  csrfToken,
  base64urlToBuffer,
  bufferToBase64url,
};

function start() {
  bindPasskeys();
  bindRabbitFlow(document);
  bindPhotoUpload(document);
  bindPhotoStep(document);
  bindDeleteDialog(document);
  bindPhotoTiles(document);
  bindDeathFields(document);
  bindOffline(document, window);
  bindSettings(document, window);
  bindSettingsSave(document, window);
  bindPairingCheck(document, window);
  bindConfirmDelete(document, window);
  bindFilters(document);
  bindMenu(document, window);
  bindQuickDone(document, window);
  bindTabEdit(document, window);
  bindToasts(document, window);
  bindUndoRemove(document, window);
  bindSwipe(document, window);
  bindWeighIn(document, window);
  bindPullRefresh(document, window);
  bindRepeatFields(document);
  bindPressReset(document, window);
  bindAccountMenu(document);
  // A link to a folded section (such as #health from the Health list) opens it.
  const openFold = () => {
    const target = location.hash && document.getElementById(location.hash.slice(1));
    const fold = target && target.closest("details[data-fold]");
    if (fold && !fold.open) {
      fold.open = true;
      // Opening grows the section after the browser has jumped; settle on it smoothly.
      requestAnimationFrame(() => target.scrollIntoView({ block: "start", behavior: reducedMotion() ? "auto" : "smooth" }));
    }
  };
  openFold();
  window.addEventListener("hashchange", openFold);
  bindPrefetch(document, window);
  bindScrollSpy(document, window);
  bindGuide();
  bindRabbitInline(document, window);
  bindSegmented(document);
  bindFamilyTree(document);
  bindListSwap(document, window);
  bindWeightsPage(document, window);
  bindSideMenu(document, window);
  bindAuthForms(document, window);
  bindLitterPhotos(document);
  bindAddSheets(document);
  bindMoreMenus(document);
  bindModal(document, window);
  // Arriving to log a weight (a swipe or the Log weight button): focus the entry.
  if (new URLSearchParams(window.location.search).has("weigh")) {
    const weigh = document.querySelector('#weights form[action$="/weights/"] input:not([type=hidden]):not([type=date])');
    window.setTimeout(() => focusSmooth(weigh), 0);
  }
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", start);
} else {
  start();
}

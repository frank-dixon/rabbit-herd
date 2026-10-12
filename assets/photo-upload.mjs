/*
 * Shrink a photo in the browser before it is uploaded.
 *
 * Vercel refuses request bodies over about 4.5 MB, and phone photos are
 * often bigger. When the browser can read the picture, it is redrawn at no
 * more than 2560 pixels on its longest side and sent as a JPEG. The server
 * still checks and cleans every file. Without JavaScript the plain form
 * posts the original file, and the help text gives the size limit.
 */

export const MAX_SIDE = 2560;
// Stay safely under Vercel's 4.5 MB limit, leaving room for the notes and form fields.
export const MAX_UPLOAD_BYTES = 4 * 1024 * 1024;
export const TOO_BIG =
  "This photo is too big to upload, even after shrinking. Please choose a photo under 4 MB.";

/** Width and height that fit inside MAX_SIDE, keeping the shape. */
export function fitWithin(width, height, maxSide = MAX_SIDE) {
  const longest = Math.max(width, height);
  if (!longest || longest <= maxSide) {
    return { width, height };
  }
  const scale = maxSide / longest;
  return { width: Math.round(width * scale), height: Math.round(height * scale) };
}

/** Whether a picture of this size and byte count should be redrawn. */
export function needsShrink(width, height, bytes) {
  return Math.max(width, height) > MAX_SIDE || bytes > MAX_UPLOAD_BYTES;
}

function loadImage(file) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => resolve({ img, url });
    img.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("unreadable"));
    };
    img.src = url;
  });
}

async function shrink(file) {
  let loaded;
  try {
    loaded = await loadImage(file);
  } catch {
    return file; // The browser can't draw it (for example HEIC on Chrome). Send it as is.
  }
  const { img, url } = loaded;
  try {
    const w = img.naturalWidth;
    const h = img.naturalHeight;
    if (!needsShrink(w, h, file.size)) {
      return file;
    }
    const size = fitWithin(w, h);
    const canvas = document.createElement("canvas");
    canvas.width = size.width;
    canvas.height = size.height;
    canvas.getContext("2d").drawImage(img, 0, 0, size.width, size.height);
    for (const quality of [0.85, 0.75, 0.6]) {
      const blob = await new Promise((done) => canvas.toBlob(done, "image/jpeg", quality));
      if (blob && blob.size <= MAX_UPLOAD_BYTES) {
        const name = (file.name || "photo").replace(/\.[^.]*$/, "") + ".jpg";
        return new File([blob], name, { type: "image/jpeg", lastModified: Date.now() });
      }
    }
    return file;
  } finally {
    URL.revokeObjectURL(url);
  }
}

function showError(input, message) {
  let box = input.form.querySelector("[data-photo-error]");
  if (!box) {
    box = document.createElement("p");
    box.setAttribute("data-photo-error", "");
    box.setAttribute("role", "alert");
    box.className = "text-sm font-medium text-red-700";
    input.insertAdjacentElement("afterend", box);
  }
  box.textContent = message;
}

export function bindPhotoUpload(root) {
  for (const input of root.querySelectorAll('[data-photo-upload] input[type="file"]')) {
    const form = input.form;
    let ready = false;
    form.addEventListener("submit", async (event) => {
      if (ready || !input.files || !input.files.length) {
        return;
      }
      event.preventDefault();
      const button = form.querySelector('[type="submit"]');
      if (button) button.disabled = true;
      try {
        const original = input.files[0];
        const file = await shrink(original);
        if (file.size > MAX_UPLOAD_BYTES) {
          showError(input, TOO_BIG);
          return;
        }
        if (file !== original && typeof DataTransfer !== "undefined") {
          const transfer = new DataTransfer();
          transfer.items.add(file);
          input.files = transfer.files;
        }
        ready = true;
        form.submit();
      } finally {
        if (button) button.disabled = false;
      }
    });
  }
}

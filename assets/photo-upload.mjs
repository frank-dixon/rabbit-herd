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
  "This photo is too big to upload, even after shrinking. Choose a photo under 4 MB.";

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

/**
 * The EXIF date a JPEG was taken ("YYYY-MM-DD"), or "". Reads
 * DateTimeOriginal, then DateTimeDigitized, then the main DateTime. Used
 * only when the browser redraws the photo, which drops its metadata; the
 * server reads the date itself from files it receives untouched.
 */
export function exifDate(buffer) {
  const view = new DataView(buffer);
  if (view.byteLength < 4 || view.getUint16(0) !== 0xffd8) return "";
  let offset = 2;
  while (offset + 4 <= view.byteLength) {
    const marker = view.getUint16(offset);
    const size = view.getUint16(offset + 2);
    if (marker === 0xffe1 && view.getUint32(offset + 4) === 0x45786966) {
      return tiffDate(view, offset + 10);
    }
    if ((marker & 0xff00) !== 0xff00 || marker === 0xffda) break;
    offset += 2 + size;
  }
  return "";
}

function tiffDate(view, start) {
  try {
    const little = view.getUint16(start) === 0x4949;
    const u16 = (at) => view.getUint16(at, little);
    const u32 = (at) => view.getUint32(at, little);
    const entries = (ifd) => {
      const found = {};
      const count = u16(start + ifd);
      for (let i = 0; i < count; i += 1) {
        const at = start + ifd + 2 + i * 12;
        found[u16(at)] = { type: u16(at + 2), count: u32(at + 4), value: u32(at + 8) };
      }
      return found;
    };
    const text = (entry) => {
      if (!entry || entry.type !== 2 || entry.count < 10) return "";
      let out = "";
      for (let i = 0; i < 10; i += 1) out += String.fromCharCode(view.getUint8(start + entry.value + i));
      return /^\d{4}:\d{2}:\d{2}$/.test(out) ? out.replace(/:/g, "-") : "";
    };
    const ifd0 = entries(u32(start + 4));
    const inner = ifd0[0x8769] ? entries(ifd0[0x8769].value) : {};
    return text(inner[0x9003]) || text(inner[0x9004]) || text(ifd0[0x0132]);
  } catch {
    return "";
  }
}

async function readDate(file) {
  try {
    return exifDate(await file.slice(0, 256 * 1024).arrayBuffer());
  } catch {
    return "";
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
        const hint = form.querySelector("[data-taken-hint]");
        if (hint) hint.value = await readDate(original);
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

/*
 * The photos card of the add-a-rabbit flow (templates/rabbits/flow/_photos.html).
 * Picked or dropped files upload one at a time, in the order picked, with a progress
 * line each; big photos are shrunk first (photo-upload.mjs) and the EXIF date travels
 * as a hint. Thumbnails reorder by drag. The page then reloads to show the new list.
 * Without JS the same form posts the files with Add photos or Next.
 */
import { MAX_UPLOAD_BYTES, TOO_BIG, readDate, shrink } from "./photo-upload.mjs";

/** The new order after dragging the photo at `from` onto the slot at `to`. */
export function moveIndex(length, from, to) {
  const order = Array.from({ length }, (_, i) => i);
  if (from === to || from < 0 || to < 0 || from >= length || to >= length) return order;
  const [item] = order.splice(from, 1);
  order.splice(to, 0, item);
  return order;
}

function post(url, data, onProgress) {
  return new Promise((resolve) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", url);
    xhr.setRequestHeader("X-Requested-With", "fetch");
    xhr.upload.onprogress = (event) => { if (event.lengthComputable) onProgress?.(event.loaded / event.total); };
    xhr.onload = () => { let body = {}; try { body = JSON.parse(xhr.responseText); } catch {} resolve({ ok: xhr.status < 400, body }); };
    xhr.onerror = () => resolve({ ok: false, body: { errors: ["The upload didn't go through. Check your connection and try again."] } });
    xhr.send(data);
  });
}

export function bindPhotoStep(root, win = window) {
  const box = root.querySelector("[data-photo-step]");
  if (!box) return;
  const form = box.closest("form");
  const input = box.querySelector("[data-photo-input]");
  const drop = box.querySelector("[data-photo-drop]");
  const progress = box.querySelector("[data-photo-progress]");
  const url = box.dataset.uploadUrl;
  const token = () => form.querySelector("[name=csrfmiddlewaretoken]")?.value || "";
  let busy = false;

  async function upload(files) {
    if (busy || !files.length) return;
    busy = true;
    const errors = [];
    for (const original of files) {
      const line = root.createElement("li");
      line.className = "flex items-center gap-2";
      line.innerHTML = '<span class="min-w-0 flex-1 truncate"></span><span class="h-1.5 w-24 overflow-hidden rounded-full bg-line"><span class="block h-full w-0 rounded-full bg-accent transition-[width] duration-150"></span></span>';
      line.firstChild.textContent = original.name;
      const bar = line.querySelector("span span");
      progress.append(line);
      const hint = await readDate(original);
      const file = await shrink(original);
      if (file.size > MAX_UPLOAD_BYTES) { errors.push(`${original.name}: ${TOO_BIG}`); line.remove(); continue; }
      const data = new FormData();
      data.append("csrfmiddlewaretoken", token());
      data.append("action", "upload");
      data.append("taken_hint", hint || "");
      data.append("photos", file, file.name);
      const { body } = await post(url, data, (p) => { bar.style.width = `${Math.round(p * 100)}%`; });
      bar.style.width = "100%";
      for (const error of body.errors || []) errors.push(error);
    }
    input.value = "";
    if (errors.length) win.sessionStorage?.setItem("photo-step-errors", JSON.stringify(errors));
    win.location.replace(`${url}?added=${Date.now()}#photos`);
  }

  input?.addEventListener("change", () => upload([...input.files]));
  // Next with files still picked (JS uploads them as they're picked, so this only guards a race).
  form.addEventListener("submit", () => { if (busy) input.value = ""; });
  if (drop) {
    for (const type of ["dragenter", "dragover"]) drop.addEventListener(type, (e) => { if (e.dataTransfer?.types?.includes("Files")) { e.preventDefault(); drop.dataset.over = ""; } });
    for (const type of ["dragleave", "drop"]) drop.addEventListener(type, () => delete drop.dataset.over);
    drop.addEventListener("drop", (e) => { e.preventDefault(); upload([...(e.dataTransfer?.files || [])].filter((f) => f.type.startsWith("image/") || /\.hei[cf]$/i.test(f.name))); });
  }
  // Errors from the last round of uploads, shown after the reload.
  const saved = win.sessionStorage?.getItem("photo-step-errors");
  if (saved) {
    win.sessionStorage.removeItem("photo-step-errors");
    for (const message of JSON.parse(saved)) {
      const li = root.createElement("li");
      li.className = "font-medium text-danger";
      li.setAttribute("role", "alert");
      li.textContent = message;
      progress.append(li);
    }
  }
  // Drag a thumbnail onto another to move it there.
  const list = box.querySelector("[data-photo-list]");
  let dragged = null;
  list?.addEventListener("dragstart", (e) => { dragged = e.target.closest("[data-photo-index]"); e.dataTransfer?.setData("text/plain", "photo"); });
  list?.addEventListener("dragover", (e) => { if (dragged) e.preventDefault(); });
  list?.addEventListener("drop", async (e) => {
    const target = e.target.closest("[data-photo-index]");
    if (!dragged || !target) return;
    e.preventDefault();
    const items = [...list.querySelectorAll("[data-photo-index]")];
    const order = moveIndex(items.length, items.indexOf(dragged), items.indexOf(target));
    dragged = null;
    const data = new FormData();
    data.append("csrfmiddlewaretoken", token());
    data.append("action", "order");
    data.append("order", order.join(","));
    await post(url, data);
    win.location.reload();
  });
}

// ---------------------------------------------------------
// drawer-effects.js
// Everything related to *how the UI behaves*:
//   - dragging the logo button anywhere on the page
//   - remembering where the user dropped it (per-tab reload persists)
//   - expanding/collapsing the drawer on click
// No backend / fetch logic belongs in this file.
// ---------------------------------------------------------

const RSDrawerEffects = (function () {
  const STORAGE_KEY = "rs_drawer_position";
  const DRAG_THRESHOLD = 4; // px of movement before we treat it as a drag, not a click

  let rootEl, logoBtn;
  let isDragging = false;
  let didDrag = false;
  let startX = 0;
  let startY = 0;
  let originLeft = 0;
  let originTop = 0;

  function init(root) {
    rootEl = root;
    logoBtn = document.getElementById("rs-logo-btn");

    restorePosition();

    logoBtn.addEventListener("mousedown", onDragStart);
    document.addEventListener("mousemove", onDragMove);
    document.addEventListener("mouseup", onDragEnd);

    logoBtn.addEventListener("click", onLogoClick);

    // Collapse the drawer if the user clicks elsewhere on the page
    document.addEventListener("click", (e) => {
      if (!rootEl.contains(e.target)) {
        rootEl.classList.remove("rs-open");
      }
    });
  }

  function onDragStart(e) {
    isDragging = true;
    didDrag = false;
    startX = e.clientX;
    startY = e.clientY;

    const rect = rootEl.getBoundingClientRect();
    originLeft = rect.left;
    originTop = rect.top;

    logoBtn.classList.add("rs-dragging");
    rootEl.classList.add("rs-dragging");
    e.preventDefault();
  }

  function onDragMove(e) {
    if (!isDragging) return;

    const dx = e.clientX - startX;
    const dy = e.clientY - startY;

    if (Math.abs(dx) > DRAG_THRESHOLD || Math.abs(dy) > DRAG_THRESHOLD) {
      didDrag = true;
    }

    if (!didDrag) return;

    let newLeft = originLeft + dx;
    let newTop = originTop + dy;

    // Keep the drawer fully within the viewport
    const maxLeft = window.innerWidth - rootEl.offsetWidth - 8;
    const maxTop = window.innerHeight - rootEl.offsetHeight - 8;
    newLeft = Math.min(Math.max(8, newLeft), Math.max(8, maxLeft));
    newTop = Math.min(Math.max(8, newTop), Math.max(8, maxTop));

    rootEl.style.left = `${newLeft}px`;
    rootEl.style.top = `${newTop}px`;
    rootEl.style.right = "auto";
  }

  function onDragEnd() {
    if (!isDragging) return;
    isDragging = false;

    logoBtn.classList.remove("rs-dragging");
    rootEl.classList.remove("rs-dragging");

    if (didDrag) {
      savePosition();
    }
  }

  function onLogoClick() {
    // A drag ending shouldn't also toggle the drawer
    if (didDrag) {
      didDrag = false;
      return;
    }
    rootEl.classList.toggle("rs-open");
  }

  function savePosition() {
    const rect = rootEl.getBoundingClientRect();
    chrome.storage.local.set({
      [STORAGE_KEY]: { left: rect.left, top: rect.top }
    });
  }

  function restorePosition() {
    chrome.storage.local.get(STORAGE_KEY, (result) => {
      const pos = result[STORAGE_KEY];
      if (pos && typeof pos.left === "number" && typeof pos.top === "number") {
        rootEl.style.left = `${pos.left}px`;
        rootEl.style.top = `${pos.top}px`;
        rootEl.style.right = "auto";
      }
      // otherwise it keeps the CSS default (top-right, near where the
      // puzzle-piece extensions icon lives)
    });
  }

  function setStatus(text, state) {
    const statusEl = document.getElementById("rs-status");
    if (!statusEl) return;
    statusEl.textContent = text;
    statusEl.classList.remove("rs-success", "rs-error");
    if (state === "success") statusEl.classList.add("rs-success");
    if (state === "error") statusEl.classList.add("rs-error");
  }

  function closeDrawer() {
    rootEl.classList.remove("rs-open");
  }

  function setButtonLoading(buttonEl, isLoading) {
    buttonEl.classList.toggle("rs-loading", isLoading);
    buttonEl.classList.toggle("rs-disabled", isLoading);
  }

  return {
    init,
    setStatus,
    closeDrawer,
    setButtonLoading
  };
})();
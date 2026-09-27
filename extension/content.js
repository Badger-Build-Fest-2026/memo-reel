// ---------------------------------------------------------
// content.js
// Responsible ONLY for building the DOM and wiring click
// handlers to the right module. No drag logic, no fetch
// logic lives here — see drawer-effects.js and reel-actions.js
// ---------------------------------------------------------

(function () {
  // Avoid double-injection if the script somehow runs twice
  if (document.getElementById("rs-root")) return;

  const root = document.createElement("div");
  root.id = "rs-root";

  root.innerHTML = `
    <div id="rs-drawer">
      <button id="rs-save-btn" class="rs-tool-btn" title="Save this Reel">
        <span class="rs-icon-wrap">📥</span>
        <span class="rs-label">Save Reel</span>
      </button>

      <button id="rs-redirect-btn" class="rs-tool-btn" title="Open your dashboard">
        <span class="rs-icon-wrap">📊</span>
        <span class="rs-label">Open Dashboard</span>
      </button>

      <div id="rs-status"></div>
    </div>

    <button id="rs-logo-btn" title="Reel Saver">
      <img src="${chrome.runtime.getURL("logo.png")}" alt="Reel Saver" />
    </button>
  `;

  document.body.appendChild(root);

  // Hand off behavior to the effects module (drag + expand/collapse)
  RSDrawerEffects.init(root);

  // Wire the two tool buttons to the actions module
  document.getElementById("rs-save-btn").addEventListener("click", () => {
    RSReelActions.saveCurrentReel();
  });

  document.getElementById("rs-redirect-btn").addEventListener("click", () => {
    RSReelActions.openDashboard();
  });
})();
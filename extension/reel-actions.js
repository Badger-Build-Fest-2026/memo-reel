// ---------------------------------------------------------
// reel-actions.js
// All logic that talks to the outside world: extracting reel
// data from the page, sending it to your FastAPI backend, and
// redirecting to your Streamlit dashboard.
// This is the direct successor of the old popup.js logic, now
// callable from the in-page drawer instead of the popup.
// ---------------------------------------------------------

const RS_BACKEND_URL = "https://recall-graph.onrender.com/";
const RS_DASHBOARD_URL = "https://your-streamlit-app.streamlit.app"; // <-- set your real URL

const RSReelActions = (function () {
  async function getOrCreateUserId() {
    const { userId } = await chrome.storage.local.get("userId");
    if (userId) return userId;

    const newId = crypto.randomUUID();
    await chrome.storage.local.set({ userId: newId });
    return newId;
  }

  function extractReelDataFromPage() {
    // Runs in the same page context as content.js, so no need
    // for chrome.scripting.executeScript / a separate injected
    // file — we can call the extractor logic directly.
    // Assumes reelExtractor.js exposes a global `extractReelData()`.
    if (typeof extractReelData !== "function") {
      throw new Error("Reel extractor not available on this page.");
    }
    return extractReelData();
  }

  async function saveCurrentReel() {
    const saveBtn = document.getElementById("rs-save-btn");

    try {
      RSDrawerEffects.setButtonLoading(saveBtn, true);
      RSDrawerEffects.setStatus("Extracting Reel...", null);

      const reelUrl = window.location.href;

      if (!reelUrl.includes("instagram.com")) {
        throw new Error("Please open an Instagram Reel first.");
      }

      const reelData = extractReelDataFromPage();
      if (!reelData) {
        throw new Error("Could not extract Reel data.");
      }

      const userId = await getOrCreateUserId();

      RSDrawerEffects.setStatus("Sending to server...", null);

      const response = await fetch(RS_BACKEND_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: userId,
          reel_url: reelUrl,
          account_name: reelData.account_name,
          caption: reelData.caption,
          hashtags: reelData.hashtags
        })
      });

      if (!response.ok) {
        throw new Error(`Server returned ${response.status}`);
      }

      const data = await response.json();
      console.log("Backend response:", data);

      RSDrawerEffects.setStatus("Saved successfully!", "success");
    } catch (error) {
      console.error(error);
      RSDrawerEffects.setStatus(`Error: ${error.message}`, "error");
    } finally {
      RSDrawerEffects.setButtonLoading(saveBtn, false);
    }
  }

  function openDashboard() {
    window.open(RS_DASHBOARD_URL, "_blank", "noopener,noreferrer");
  }

  return {
    saveCurrentReel,
    openDashboard
  };
})();
// ---------------------------------------------------------
// reel-actions.js
// All logic that talks to the outside world: extracting reel
// data from the page, sending it to your FastAPI backend, and
// redirecting to your Streamlit dashboard.
// ---------------------------------------------------------

// const RS_BACKEND_URL = "https://recall-graph.onrender.com/api/v1/reels/submit";
const RS_BACKEND_URL = "https://localhost:8000/api/v1/reels/submit";
const RS_DASHBOARD_URL = "https://your-streamlit-app.streamlit.app"; // <-- set your real URL

const RSReelActions = (function () {
  function getOrCreateUserId() {
    let userId = localStorage.getItem("rs_userId");
    if (!userId) {
      userId = crypto.randomUUID();
      localStorage.setItem("rs_userId", userId);
    }
    return userId;
  }

  function extractReelDataFromPage(userId) {
    if (typeof extractReelData !== "function") {
      throw new Error("Reel extractor not available on this page.");
    }
    return extractReelData(userId);
  }

  async function saveCurrentReel() {
    const saveBtn = document.getElementById("rs-save-btn");

    try {
      RSDrawerEffects.setButtonLoading(saveBtn, true);
      RSDrawerEffects.setStatus("Extracting Reel...", null);

      if (!window.location.href.includes("instagram.com")) {
        throw new Error("Please open an Instagram Reel first.");
      }

      const userId = getOrCreateUserId();

      const reelData = extractReelDataFromPage(userId);
      if (!reelData) {
        throw new Error("Could not extract Reel data.");
      }

      RSDrawerEffects.setStatus("Sending to server...", null);

      // Convert array of hashtags to string to match backend schema (hashtags: str)
      const payload = {
        user_id: reelData.user_id,
        account_name: reelData.account_name || "",
        source_url: reelData.source_url,
        hashtags: Array.isArray(reelData.hashtags) ? reelData.hashtags.join(" ") : "",
        caption: reelData.caption || "",
        requested_at: reelData.requested_at
      };

      const response = await fetch(RS_BACKEND_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        const errorText = await response.text();
        console.error("Server Error Detail:", errorText);
        throw new Error(`Server returned ${response.status}`);
      }

      // ---------------------------------------------------------
      // Read & console.log the response payload from FastAPI
      // ---------------------------------------------------------
      const responseData = await response.json();

      console.group("%c[Reel Saver] Backend Response Accepted", "color: #0087ff; font-weight: bold;");
      console.log("Capture ID:", responseData.capture_id);
      console.log("Status:", responseData.status);
      console.log("Job Status:", responseData.job_status);
      console.log("Full Payload:", responseData);
      console.groupEnd();

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
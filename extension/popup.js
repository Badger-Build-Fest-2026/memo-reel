document.getElementById("submit").addEventListener("click", async () => {
  const status = document.getElementById("status");

  try {
    status.textContent = "Extracting Reel...";

    // ---------------------------------------------------------
    // 1. Get the current tab
    // ---------------------------------------------------------

    const [tab] = await chrome.tabs.query({
      active: true,
      currentWindow: true
    });

    if (!tab || !tab.id) {
      throw new Error("Could not find the active tab.");
    }

    const reelUrl = tab.url;

    if (!reelUrl || !reelUrl.includes("instagram.com")) {
      throw new Error("Please open an Instagram Reel first.");
    }

    // ---------------------------------------------------------
    // 2. Extract Reel data from the Instagram page
    // ---------------------------------------------------------

    const results = await chrome.scripting.executeScript({
      target: {
        tabId: tab.id
      },
      files: ["reelExtractor.js"]
    });

    if (!results || !results[0] || !results[0].result) {
      throw new Error("Could not extract Reel data.");
    }

    const reelData = results[0].result;

    console.log("Extracted Reel data:", reelData);

    // ---------------------------------------------------------
    // 3. Get or create a unique ID for this extension
    //    installation
    // ---------------------------------------------------------

    let { userId } = await chrome.storage.local.get("userId");

    if (!userId) {
      userId = crypto.randomUUID();

      await chrome.storage.local.set({
        userId: userId
      });
    }

    // ---------------------------------------------------------
    // 4. Send the data to FastAPI
    // ---------------------------------------------------------

    status.textContent = "Sending to server...";

    const response = await fetch(
      "http://0.0.0.0:8287/api/v1/reels",
      {
        method: "POST",

        headers: {
          "Content-Type": "application/json"
        },

        body: JSON.stringify({
          user_id: userId,

          reel_url: reelUrl,

          account_name: reelData.account_name,

          caption: reelData.caption,

          hashtags: reelData.hashtags
        })
      }
    );

    // ---------------------------------------------------------
    // 5. Handle HTTP errors
    // ---------------------------------------------------------

    if (!response.ok) {
      throw new Error(
        `Server returned ${response.status}`
      );
    }

    // ---------------------------------------------------------
    // 6. Read backend response
    // ---------------------------------------------------------

    const data = await response.json();

    console.log("Backend response:", data);

    status.textContent = "Submitted successfully!";

  } catch (error) {
    console.error(error);

    status.textContent = `Error: ${error.message}`;
  }
});
/**
 * Extract information from the Instagram Reel currently open
 * on the page, plus request metadata (reel URL, timestamp,
 * and the caller-supplied userId).
 *
 * @param {string} userId - persistent per-install ID generated from localStorage
 *
 * Returns:
 * {
 *   account_name: string | null,
 *   caption: string | null,
 *   hashtags: string[],
 *   source_url: string,
 *   user_id: string,
 *   requested_at: string // ISO 8601
 * }
 */
function extractReelData(userId) {
  // System route names on Instagram to exclude when searching for user profile links
  const SYSTEM_PATHS = new Set([
    "",
    "explore",
    "reels",
    "reel",
    "stories",
    "direct",
    "p",
    "tv",
    "accounts",
    "developer",
    "about",
    "privacy",
    "terms"
  ]);

  // Helper to extract clean path from an href (removes query strings & leading/trailing slashes)
  function getCleanPath(href) {
    if (!href) return "";
    return href
      .split("?")[0]
      .split("#")[0]
      .replace(/^\/+|\/+$/g, "");
  }

  // ------------------------------------------------------------
  // 1. Find the Reel link
  // ------------------------------------------------------------

  const reelLink = Array.from(document.querySelectorAll("a[href]")).find(link => {
    const href = link.getAttribute("href");
    return href && /^\/[^/]+\/(?:reels?)\/[^/]+\/?/.test(href);
  });

  // ------------------------------------------------------------
  // 2. Find the Reel container
  // ------------------------------------------------------------

  let container = reelLink ? reelLink.parentElement : document.body;

  if (reelLink) {
    while (container && container !== document.body) {
      const profileLink = Array.from(
        container.querySelectorAll("a[href]")
      ).find(link => {
        const cleanPath = getCleanPath(link.getAttribute("href"));
        return (
          cleanPath.length > 0 &&
          !cleanPath.includes("/") &&
          !SYSTEM_PATHS.has(cleanPath)
        );
      });

      if (profileLink) break;
      container = container.parentElement;
    }
  }

  if (!container) {
    container = document.body;
  }

  // ------------------------------------------------------------
  // 3. Find author profile link
  // ------------------------------------------------------------

  // Priority 1: Match standard Instagram author profile class `_a6hd`
  let profileLink = Array.from(
    container.querySelectorAll('a._a6hd[href], a[href].notranslate')
  ).find(link => {
    const cleanPath = getCleanPath(link.getAttribute("href"));
    return (
      cleanPath.length > 0 &&
      !cleanPath.includes("/") &&
      !SYSTEM_PATHS.has(cleanPath)
    );
  });

  // Priority 2: Fallback to searching all links inside container
  if (!profileLink) {
    profileLink = Array.from(container.querySelectorAll("a[href]")).find(
      link => {
        const cleanPath = getCleanPath(link.getAttribute("href"));
        return (
          cleanPath.length > 0 &&
          !cleanPath.includes("/") &&
          !SYSTEM_PATHS.has(cleanPath)
        );
      }
    );
  }

  if (!profileLink) {
    throw new Error("Could not find author profile link.");
  }

  // ------------------------------------------------------------
  // 4. Extract account name
  // ------------------------------------------------------------

  let accountName = null;

  // Try extracting from inner span/text nodes first (e.g., <span dir="auto">wasted</span>)
  const textContainer =
    profileLink.querySelector('span[dir="auto"]') ||
    profileLink.querySelector("span") ||
    profileLink;

  if (textContainer && textContainer.textContent.trim()) {
    accountName = textContainer.textContent.trim();
  }

  // Fallback: Parse directly from href (e.g. href="/wasted/?hl=en" -> "wasted")
  if (!accountName || SYSTEM_PATHS.has(accountName.toLowerCase())) {
    const rawHref = profileLink.getAttribute("href");
    const cleanUsername = getCleanPath(rawHref);

    if (cleanUsername && !SYSTEM_PATHS.has(cleanUsername)) {
      accountName = cleanUsername;
    }
  }

  let captionElement = null;

  const lineStyleSpans = Array.from(
    document.querySelectorAll('span[style*="line-height"]')
  ).filter(span => {
    const style = (span.getAttribute("style") || "").replace(/\s+/g, "");
    const text = span.textContent.trim();
    return style.includes("line-height:18px") && text.length > 20;
  });

  if (lineStyleSpans.length > 0) {
    captionElement = lineStyleSpans.sort(
      (a, b) => b.textContent.trim().length - a.textContent.trim().length
    )[0];
  }

  // Fallback if no line-height style span found
  if (!captionElement) {
    const allSpans = Array.from(document.querySelectorAll("span")).filter(span => {
      const text = span.textContent.trim();
      if (text.length < 30) return false;
      if (span.querySelector("time, button, input")) return false;
      return true;
    });

    if (allSpans.length > 0) {
      captionElement = allSpans.sort(
        (a, b) => b.textContent.trim().length - a.textContent.trim().length
      )[0];
    }
  }

  // ------------------------------------------------------------
  // 6. Clean Caption Text (Strip Account Name & Timestamp)
  // ------------------------------------------------------------

  function getCleanCaptionText(element, accountNameStr) {
    if (!element) return "";

    const clone = element.cloneNode(true);

    // 1. Remove all timestamp <time> tags and buttons
    clone.querySelectorAll("time, button, a._a6hd").forEach(el => el.remove());

    // 2. Convert <br> tags to newlines
    clone.querySelectorAll("br").forEach(br => {
      br.replaceWith("\n");
    });

    let rawText = clone.textContent
      .replace(/\u00a0/g, " ")
      .replace(/\r/g, "")
      .replace(/[ \t]+\n/g, "\n")
      .replace(/\n[ \t]+/g, "\n")
      .trim();

    // 3. Strip leading account name if present at start of text
    if (accountNameStr && rawText.toLowerCase().startsWith(accountNameStr.toLowerCase())) {
      rawText = rawText.slice(accountNameStr.length).trim();
    }

    // 4. Strip leading Instagram relative timestamp patterns (e.g. "41w", "2d", "10h", "15m", "1y")
    rawText = rawText.replace(/^(\d+[smhdwy]|•|\s)+/i, "").trim();

    return rawText;
  }

  const caption = getCleanCaptionText(captionElement, accountName);

  // ------------------------------------------------------------
  // 7. Extract hashtags
  // ------------------------------------------------------------

  const hashtags = caption
    ? [...caption.matchAll(/#[\p{L}\p{N}_]+/gu)].map(match => match[0])
    : [];

  // ------------------------------------------------------------
  // 8. Final Payload
  // ------------------------------------------------------------

  const result = {
    account_name: accountName || "",
    caption: caption,
    hashtags: hashtags,
    source_url: window.location.href,
    user_id: userId,
    requested_at: new Date().toISOString()
  };

  console.log("Instagram Reel Extracted:", result);

  return result;
}
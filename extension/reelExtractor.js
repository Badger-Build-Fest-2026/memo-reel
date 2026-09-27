/**
 * Extract metadata from the Reel currently playing in the Instagram page.
 * Missing captions are returned as an empty string; unrelated page text is
 * never used as a substitute.
 *
 * @param {string} userId - Persistent per-install ID generated from localStorage.
 */
function extractReelData(userId) {
  function cleanText(value) {
    return value.replace(/\u00a0/g, " ").replace(/\s+/g, " ").trim();
  }

  function cleanCaption(value) {
    return value
      .replace(/\u00a0/g, " ")
      .split(/\r?\n/)
      .map(line => line.replace(/[ \t]+/g, " ").trim())
      .filter(Boolean)
      .join("\n");
  }

  const systemPaths = new Set([
    "",
    "about",
    "accounts",
    "developer",
    "direct",
    "explore",
    "p",
    "privacy",
    "profile",
    "reel",
    "reels",
    "stories",
    "terms",
    "tv"
  ]);
  const reelMatch = window.location.pathname.match(
    /^\/reels?\/([A-Za-z0-9_-]+)\/?$/
  );
  if (!reelMatch) {
    throw new Error("Open an Instagram Reel before saving.");
  }

  function visible(element) {
    const rect = element.getBoundingClientRect();
    const style = window.getComputedStyle(element);
    return (
      rect.width > 0 &&
      rect.height > 0 &&
      style.display !== "none" &&
      style.visibility !== "hidden"
    );
  }

  function getUsernameFromLink(link) {
    const href = link.getAttribute("href") || "";
    const path = href.split(/[?#]/, 1)[0];
    const match = path.match(
      /^\/([A-Za-z0-9._]+)(?:\/(reels|tagged|followers|following))?\/?$/
    );
    if (match && !systemPaths.has(match[1].toLowerCase())) {
      return match[1];
    }

    const label = link.getAttribute("aria-label") || "";
    const labelMatch = label.match(
      /^([A-Za-z0-9._]+)\s+(?:reels|profile)$/i
    );
    if (labelMatch && !systemPaths.has(labelMatch[1].toLowerCase())) {
      return labelMatch[1];
    }

    return null;
  }

  const videos = Array.from(document.querySelectorAll("video")).filter(visible);
  const activeVideo =
    videos.find(video => !video.paused && video.currentTime > 0) || videos[0];
  if (!activeVideo) {
    throw new Error("Could not locate the active Reel video.");
  }

  let reelContainer = activeVideo.parentElement;
  let profileLink = null;
  let username = null;
  while (reelContainer && reelContainer !== document.body) {
    const profileLinks = Array.from(
      reelContainer.querySelectorAll("a[href]")
    )
      .map(link => ({ link, username: getUsernameFromLink(link) }))
      .filter(candidate => candidate.username && visible(candidate.link));

    if (profileLinks.length > 0) {
      profileLink = profileLinks[0].link;
      username = profileLinks[0].username;
      break;
    }
    reelContainer = reelContainer.parentElement;
  }

  if (!username || !reelContainer) {
    throw new Error("Could not identify the Reel author's profile.");
  }

  const hashtagLinkSelector = 'a[href*="/explore/tags/"]';
  const captionBlocks = Array.from(
    reelContainer.querySelectorAll('[dir="auto"]')
  )
    .filter(visible)
    .filter(element => !profileLink.contains(element))
    .map(element => {
      const hashtagLinks = Array.from(
        element.querySelectorAll(hashtagLinkSelector)
      );
      const clone = element.cloneNode(true);
      clone.querySelectorAll(hashtagLinkSelector).forEach(link => link.remove());
      clone.querySelectorAll("br").forEach(lineBreak => {
        lineBreak.replaceWith("\n");
      });
      const text = (clone.innerText || clone.textContent)
        .replace(/\u00a0/g, " ")
        .replace(/[ \t]+\n/g, "\n")
        .trim();
      const linkedHashtags = hashtagLinks
        .map(link => cleanText(link.textContent))
        .filter(tag => /^#[\p{L}\p{N}_]+$/u.test(tag));
      return { text, linkedHashtags };
    })
    .filter(candidate => candidate.text.length >= 20)
    .sort(
      (left, right) =>
        right.linkedHashtags.length - left.linkedHashtags.length ||
        left.text.length - right.text.length
    );

  const captionBlock = captionBlocks[0];
  const accountName = cleanText(username);
  const caption = cleanCaption(captionBlock?.text || "");
  const hashtags = captionBlock?.linkedHashtags.length
    ? [...new Set(captionBlock.linkedHashtags.map(cleanText).filter(Boolean))]
    : [
        ...new Set(
          [...caption.matchAll(/#[\p{L}\p{N}_]+/gu)]
            .map(match => cleanText(match[0]))
            .filter(Boolean)
        )
      ];
  const sourceUrl = `https://www.instagram.com/reel/${reelMatch[1]}/`;
  console.log("Extracted Reel data:", {
    account_name: accountName,
    caption,
    hashtags,
    source_url: sourceUrl,
    user_id: userId
  });
  return {
    account_name: accountName,
    caption,
    hashtags,
    source_url: sourceUrl,
    user_id: userId,
    requested_at: new Date().toISOString()
  };
}

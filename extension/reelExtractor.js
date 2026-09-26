/**
 * Extract information from the Instagram Reel currently open
 * in the active Instagram tab.
 *
 * Returns:
 * {
 *   account_name: string | null,
 *   caption: string | null,
 *   hashtags: string[]
 * }
 */
function extractInstagramReel() {

  // ------------------------------------------------------------
  // 1. Find the Reel link
  // ------------------------------------------------------------

  const reelLink = Array.from(
    document.querySelectorAll('a[href]')
  ).find(link => {
    const href = link.getAttribute("href");
    return href && /^\/[^/]+\/reel\/[^/]+\/?$/.test(href);
  });

  // ------------------------------------------------------------
  // 2. Find the Reel container
  // ------------------------------------------------------------

  let container = reelLink ? reelLink.parentElement : document.body;

  if (reelLink) {
    while (container && container !== document.body) {
      const profileLink = Array.from(
        container.querySelectorAll('a[href]')
      ).find(link => {
        const href = link.getAttribute("href");
        return href && /^\/[^/]+\/?$/.test(href);
      });

      if (profileLink) {
        break;
      }

      container = container.parentElement;
    }
  }

  if (!container) {
    container = document.body;
  }

  // ------------------------------------------------------------
  // 3. Find author profile link
  // ------------------------------------------------------------

  const profileLink = Array.from(
    container.querySelectorAll('a[href]')
  ).find(link => {
    const href = link.getAttribute("href");
    return href && /^\/[^/]+\/?$/.test(href);
  });

  if (!profileLink) {
    throw new Error("Could not find author profile link.");
  }

  // ------------------------------------------------------------
  // 4. Extract account name
  // ------------------------------------------------------------

  let accountName = null;

  const usernameSpan = profileLink.querySelector(
    'span[dir="auto"]'
  );

  if (usernameSpan) {
    accountName = usernameSpan.textContent.trim();
  } else {
    const href = profileLink.getAttribute("href");
    if (href) {
      accountName = href
        .replace(/^\/+/, "")
        .replace(/\/+$/, "");
    }
  }

  // ------------------------------------------------------------
  // 5. Extract Caption (targeted directly within author wrapper)
  // ------------------------------------------------------------

  let captionElement = null;

  /*
   * Step 5A: Find the outer span[dir="auto"] that wraps BOTH
   * the profile link AND the caption text.
   */
  const parentWrapper = profileLink.closest('span[dir="auto"]');

  if (parentWrapper) {
    /*
     * Look for child spans inside this parent wrapper that DO NOT
     * contain the profileLink, username, or timestamp (<time>).
     */
    const captionCandidates = Array.from(
      parentWrapper.querySelectorAll('span')
    ).filter(span => {
      // Must contain text
      if (!span.textContent.trim()) return false;
      // Cannot contain the profile link
      if (span.contains(profileLink) || profileLink.contains(span)) return false;
      // Cannot contain the timestamp
      if (span.querySelector('time') || span.closest('time')) return false;
      // Cannot contain inner spans (we want the leaf node holding the text)
      if (span.querySelector('span')) return false;

      return true;
    });

    if (captionCandidates.length > 0) {
      // Pick the longest text span inside the wrapper (the caption)
      captionElement = captionCandidates.sort(
        (a, b) => b.textContent.trim().length - a.textContent.trim().length
      )[0];
    }
  }

  /*
   * Step 5B: Fallback if Instagram structure varies slightly
   */
  if (!captionElement) {
    const fallbackSpans = Array.from(
      container.querySelectorAll('span')
    ).filter(span => {
      if (!span.textContent.trim()) return false;
      if (profileLink.contains(span) || span.contains(profileLink)) return false;
      if (span.querySelector('a, button, time, span')) return false;
      return true;
    });

    if (fallbackSpans.length > 0) {
      captionElement = fallbackSpans.sort(
        (a, b) => b.textContent.trim().length - a.textContent.trim().length
      )[0];
    }
  }

  // ------------------------------------------------------------
  // 6. Convert <br> tags and extract plain text
  // ------------------------------------------------------------

  function getText(element) {
    const clone = element.cloneNode(true);

    clone.querySelectorAll("br").forEach(br => {
      br.replaceWith("\n");
    });

    return clone.textContent
      .replace(/\u00a0/g, " ")
      .replace(/\r/g, "")
      .replace(/[ \t]+\n/g, "\n")
      .replace(/\n[ \t]+/g, "\n")
      .trim();
  }

  const caption = captionElement ? getText(captionElement) : null;

  // ------------------------------------------------------------
  // 7. Extract hashtags
  // ------------------------------------------------------------

  const hashtags = caption
    ? [...caption.matchAll(/#[\p{L}\p{N}_]+/gu)].map(match => match[0])
    : [];

  // ------------------------------------------------------------
  // 8. Result
  // ------------------------------------------------------------

  const result = {
    account_name: accountName,
    caption: caption,
    hashtags: hashtags
  };

  console.log("Instagram Reel Extracted:", result);

  return result;
}

extractInstagramReel();
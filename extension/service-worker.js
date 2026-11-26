const ALLOWED_HOSTS = new Set(["www.learnedleague.com", "learnedleague.com"]);

function isAllowedLearnedLeagueUrl(rawUrl) {
  try {
    const parsed = new URL(String(rawUrl || "").trim());
    return (
      parsed.protocol === "https:" &&
      ALLOWED_HOSTS.has(parsed.hostname.toLowerCase())
    );
  } catch {
    return false;
  }
}

function parseAuthFromHomeHtml(html) {
  const anchorRe = /<a\b([^>]*)>([\s\S]*?)<\/a>/gi;
  let match;
  while ((match = anchorRe.exec(html)) !== null) {
    const attrs = match[1] || "";
    const inner = match[2] || "";
    if (!/\bclass\s*=\s*["'][^"']*\bflag\b[^"']*["']/i.test(attrs)) {
      continue;
    }
    const hrefMatch = attrs.match(/\bhref\s*=\s*["']([^"']+)["']/i);
    if (!hrefMatch) continue;
    const pidMatch = hrefMatch[1].match(/profiles\.php\?(\d+)/i);
    if (!pidMatch) continue;

    const profileId = pidMatch[1];
    const titleMatch = inner.match(/\btitle\s*=\s*["']([^"']+)["']/i);
    const strippedText = inner.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim();
    const formattedUsername = (titleMatch ? titleMatch[1].trim() : "") || strippedText || profileId;

    return {
      authenticated: true,
      profile_id: profileId,
      formatted_username: formattedUsername,
      username: formattedUsername.toLowerCase(),
    };
  }
  return {
    authenticated: false,
    profile_id: null,
    formatted_username: null,
    username: null,
  };
}

async function handleCheckAuth() {
  const resp = await fetch("https://www.learnedleague.com/", {
    credentials: "include",
  });
  if (!resp.ok) {
    return {
      authenticated: false,
      status: resp.status,
      error: `LearnedLeague returned HTTP ${resp.status}`,
    };
  }
  const html = await resp.text();
  const parsed = parseAuthFromHomeHtml(html);

  if (parsed.authenticated && parsed.profile_id) {
    try {
      const profResp = await fetch(
        `https://www.learnedleague.com/profiles.php?${parsed.profile_id}&1`,
        { credentials: "include" }
      );
      if (profResp.ok) {
        const profHtml = await profResp.text();
        const nameMatch = profHtml.match(
          /<h1\b[^>]*class\s*=\s*["'][^"']*\bnamecss\b[^"']*["'][^>]*>([\s\S]*?)<\/h1>/i
        );
        if (nameMatch) {
          const cleanName = nameMatch[1].replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim();
          if (cleanName) {
            parsed.formatted_username = cleanName;
            parsed.username = cleanName.toLowerCase();
          }
        }
      }
    } catch {
      // Keep homepage flag name fallback
    }
  }

  return parsed;
}

async function handleFetchText(url) {
  if (!isAllowedLearnedLeagueUrl(url)) {
    throw new Error("Only https://learnedleague.com URLs are permitted.");
  }
  const resp = await fetch(url, { credentials: "include" });
  const body = await resp.text();
  return {
    ok: resp.ok,
    status: resp.status,
    final_url: resp.url || url,
    body,
  };
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  (async () => {
    try {
      if (!message || typeof message !== "object") {
        sendResponse({ ok: false, error: "Invalid message." });
        return;
      }
      if (message.type === "CHECK_AUTH") {
        const data = await handleCheckAuth();
        sendResponse({ ok: true, data });
        return;
      }
      if (message.type === "FETCH_TEXT") {
        const data = await handleFetchText(message.url);
        sendResponse({ ok: true, data });
        return;
      }
      sendResponse({ ok: false, error: `Unknown message type: ${String(message.type)}` });
    } catch (err) {
      sendResponse({
        ok: false,
        error: err instanceof Error ? err.message : String(err),
      });
    }
  })();
  return true;
});

const DEFAULT_APP_URL = "http://localhost:5173";
const APP_URL_KEY = "ll_bridge_app_url";

async function refreshAuthStatus() {
  const badge = document.getElementById("status-badge");
  const detail = document.getElementById("status-detail");
  badge.className = "badge warn";
  badge.textContent = "Checking session...";
  detail.textContent = "";

  try {
    const resp = await chrome.runtime.sendMessage({ type: "CHECK_AUTH" });
    if (resp && resp.ok && resp.data && resp.data.authenticated) {
      badge.className = "badge ok";
      badge.textContent = `Signed in: ${resp.data.formatted_username}`;
      detail.textContent = `Profile ID: ${resp.data.profile_id}`;
    } else {
      badge.className = "badge warn";
      badge.textContent = "Not signed in on learnedleague.com";
      detail.textContent =
        (resp && resp.data && resp.data.error) ||
        "Sign in on learnedleague.com first, then connect inside the app.";
    }
  } catch (err) {
    badge.className = "badge warn";
    badge.textContent = "Could not check session";
    detail.textContent = err instanceof Error ? err.message : String(err);
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  const urlInput = document.getElementById("app-url");
  const stored = await chrome.storage.local.get(APP_URL_KEY);
  urlInput.value = stored[APP_URL_KEY] || DEFAULT_APP_URL;

  urlInput.addEventListener("change", async () => {
    const val = urlInput.value.trim() || DEFAULT_APP_URL;
    await chrome.storage.local.set({ [APP_URL_KEY]: val });
  });

  document.querySelectorAll("[data-url]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const val = btn.dataset.url || DEFAULT_APP_URL;
      urlInput.value = val;
      await chrome.storage.local.set({ [APP_URL_KEY]: val });
    });
  });

  document.getElementById("open-app-btn").addEventListener("click", async () => {
    const val = urlInput.value.trim() || DEFAULT_APP_URL;
    await chrome.storage.local.set({ [APP_URL_KEY]: val });
    await chrome.tabs.create({ url: val });
  });

  document.getElementById("open-ll-btn").addEventListener("click", async () => {
    await chrome.tabs.create({ url: "https://www.learnedleague.com/ucp.php?mode=login" });
  });

  document.getElementById("refresh-btn").addEventListener("click", async () => {
    await refreshAuthStatus();
  });

  await refreshAuthStatus();
});

import type { AuthMe, PlayerProfile } from "../types";

const PROFILE_CACHE_TTL_MS = 30 * 60 * 1000;
const EXT_DISCONNECTED_KEY = "ll-ext-disconnected";

let activeExtensionAuth: AuthMe | null = null;
const profileCache = new Map<string, { data: PlayerProfile; ts: number }>();

export function getExtensionAuth(): AuthMe | null {
  return activeExtensionAuth;
}

export function isExtensionAuthActive(): boolean {
  return Boolean(activeExtensionAuth && activeExtensionAuth.authenticated);
}

export function isExtensionManuallyDisconnected(): boolean {
  try {
    return sessionStorage.getItem(EXT_DISCONNECTED_KEY) === "1";
  } catch {
    return false;
  }
}

export function setExtensionAuth(auth: AuthMe | null): void {
  activeExtensionAuth = auth && auth.authenticated ? auth : null;
  if (activeExtensionAuth) {
    try {
      sessionStorage.removeItem(EXT_DISCONNECTED_KEY);
    } catch {
      // Ignore storage errors
    }
  } else {
    profileCache.clear();
  }
}

export function disconnectExtension(): void {
  activeExtensionAuth = null;
  profileCache.clear();
  try {
    sessionStorage.setItem(EXT_DISCONNECTED_KEY, "1");
  } catch {
    // Ignore storage errors
  }
}

export function getCachedExtProfile(
  lookupKey: string,
  forceRefresh = false
): PlayerProfile | null {
  if (forceRefresh) return null;
  const entry = profileCache.get(lookupKey.trim().toLowerCase());
  if (!entry) return null;
  if (Date.now() - entry.ts > PROFILE_CACHE_TTL_MS) {
    profileCache.delete(lookupKey.trim().toLowerCase());
    return null;
  }
  return entry.data;
}

export function setCachedExtProfile(profile: PlayerProfile): void {
  const entry = { data: profile, ts: Date.now() };
  const keys = [
    profile.profile_id,
    profile.username,
    profile.formatted_username,
  ]
    .map((k) => (k || "").trim().toLowerCase())
    .filter(Boolean);
  for (const k of new Set(keys)) {
    profileCache.set(k, entry);
  }
}

export function detectExtension(timeoutMs = 500): Promise<boolean> {
  return new Promise((resolve) => {
    let settled = false;
    const onMessage = (event: MessageEvent) => {
      if (event.source !== window) return;
      const msg = event.data as { type?: string } | null;
      if (msg && msg.type === "LL_EXT_PONG") {
        settled = true;
        window.removeEventListener("message", onMessage);
        window.clearTimeout(timer);
        resolve(true);
      }
    };
    const timer = window.setTimeout(() => {
      if (!settled) {
        window.removeEventListener("message", onMessage);
        resolve(false);
      }
    }, timeoutMs);

    window.addEventListener("message", onMessage);
    window.postMessage({ type: "LL_EXT_PING" }, window.location.origin);
  });
}

function sendExtensionRequest<T>(
  type: "LL_EXT_CHECK_AUTH" | "LL_EXT_FETCH_TEXT",
  payload: Record<string, unknown> = {},
  timeoutMs = 30_000
): Promise<T> {
  return new Promise((resolve, reject) => {
    const requestId =
      typeof crypto !== "undefined" && "randomUUID" in crypto
        ? crypto.randomUUID()
        : `${Date.now()}-${Math.random().toString(36).slice(2)}`;

    const onMessage = (event: MessageEvent) => {
      if (event.source !== window) return;
      const msg = event.data as {
        type?: string;
        requestId?: string;
        ok?: boolean;
        data?: T;
        error?: string;
      } | null;
      if (!msg || msg.type !== "LL_EXT_RESPONSE" || msg.requestId !== requestId) {
        return;
      }
      window.removeEventListener("message", onMessage);
      window.clearTimeout(timer);
      if (msg.ok) {
        resolve(msg.data as T);
      } else {
        reject(new Error(msg.error || "Extension request failed."));
      }
    };

    const timer = window.setTimeout(() => {
      window.removeEventListener("message", onMessage);
      reject(
        new Error(
          "Timed out waiting for the LearnedLeague Chrome Extension. Ensure it is installed and enabled."
        )
      );
    }, timeoutMs);

    window.addEventListener("message", onMessage);
    window.postMessage({ type, requestId, ...payload }, window.location.origin);
  });
}

export async function extCheckAuth(): Promise<AuthMe> {
  const res = await sendExtensionRequest<{
    authenticated: boolean;
    username: string | null;
    formatted_username: string | null;
    profile_id: string | null;
    error?: string;
  }>("LL_EXT_CHECK_AUTH");

  if (!res.authenticated || !res.profile_id) {
    throw new Error(
      res.error ||
        "Not signed in on learnedleague.com in Chrome. Please log in there first."
    );
  }

  return {
    authenticated: true,
    username: res.username,
    formatted_username: res.formatted_username,
    profile_id: res.profile_id,
    desktop_keychain_available: false,
    has_saved_keychain_session: false,
    has_legacy_login_file: false,
  };
}

export async function extFetchText(url: string): Promise<string> {
  const res = await sendExtensionRequest<{
    ok: boolean;
    status: number;
    final_url: string;
    body: string;
  }>("LL_EXT_FETCH_TEXT", { url });

  if (res.status === 403) {
    throw new Error(
      "LearnedLeague returned HTTP 403 in Chrome. Open learnedleague.com to refresh any security check, then retry."
    );
  }
  if (res.status === 404) {
    throw new Error(`Resource not found on LearnedLeague: ${url}`);
  }
  if (res.status >= 400 || !res.ok) {
    throw new Error(`LearnedLeague returned HTTP ${res.status}.`);
  }
  if ((res.final_url || "").toLowerCase().includes("ucp.php?mode=login")) {
    throw new Error(
      "Your learnedleague.com session expired in Chrome. Sign in on learnedleague.com and reconnect."
    );
  }
  return res.body || "";
}

const EXTENSION_VERSION = "1.0.0";

window.addEventListener("message", async (event) => {
  if (event.source !== window) return;
  const msg = event.data;
  if (!msg || typeof msg !== "object") return;

  if (msg.type === "LL_EXT_PING") {
    window.postMessage(
      { type: "LL_EXT_PONG", version: EXTENSION_VERSION },
      window.location.origin
    );
    return;
  }

  if (msg.type !== "LL_EXT_CHECK_AUTH" && msg.type !== "LL_EXT_FETCH_TEXT") {
    return;
  }

  const requestId = msg.requestId;
  if (!requestId) return;

  try {
    const payload =
      msg.type === "LL_EXT_CHECK_AUTH"
        ? { type: "CHECK_AUTH" }
        : { type: "FETCH_TEXT", url: msg.url };

    const resp = await chrome.runtime.sendMessage(payload);
    window.postMessage(
      {
        type: "LL_EXT_RESPONSE",
        requestId,
        ok: Boolean(resp && resp.ok),
        data: resp ? resp.data : null,
        error: resp && !resp.ok ? resp.error || "Extension request failed." : null,
      },
      window.location.origin
    );
  } catch (err) {
    window.postMessage(
      {
        type: "LL_EXT_RESPONSE",
        requestId,
        ok: false,
        data: null,
        error: err instanceof Error ? err.message : String(err),
      },
      window.location.origin
    );
  }
});

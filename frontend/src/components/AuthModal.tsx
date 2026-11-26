import { useEffect, useState } from "react";
import { Globe, Puzzle, ShieldCheck } from "lucide-react";

import { api, ApiError } from "../api/client";
import {
  detectExtension,
  extCheckAuth,
  setExtensionAuth,
} from "../api/extensionBridge";
import type { AuthMe } from "../types";
import { ModalDialog } from "./ModalDialog";

interface AuthModalProps {
  open: boolean;
  onClose: () => void;
  mode: "web" | "desktop";
  onSuccess: (auth: AuthMe) => void;
}

export function AuthModal({ open, onClose, mode, onSuccess }: AuthModalProps) {
  const [busy, setBusy] = useState(false);
  const [interactiveWaiting, setInteractiveWaiting] = useState(false);
  const [extDetected, setExtDetected] = useState<boolean | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!open) {
      setInteractiveWaiting(false);
      setBusy(false);
      return;
    }
    setError("");
    if (mode !== "web") {
      setExtDetected(false);
      return;
    }
    let cancelled = false;
    setExtDetected(null);
    detectExtension(400).then((found) => {
      if (!cancelled) {
        setExtDetected(found);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [open, mode]);

  useEffect(() => {
    if (!open || mode !== "desktop" || !interactiveWaiting) return;
    let cancelled = false;
    const timer = window.setInterval(async () => {
      try {
        const res = await api.getInteractiveLoginStatus();
        if (cancelled) return;
        if (res.authenticated) {
          setInteractiveWaiting(false);
          setBusy(false);
          onSuccess(res);
          onClose();
        } else if (res.status === "stopped") {
          setInteractiveWaiting(false);
          setBusy(false);
          setError("Login window was closed before sign-in completed.");
        }
      } catch (err) {
        if (cancelled) return;
        setInteractiveWaiting(false);
        setBusy(false);
        setError(
          err instanceof ApiError ? err.message : "Failed checking login status."
        );
      }
    }, 1500);

    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [open, mode, interactiveWaiting, onSuccess, onClose]);

  const handleStartInteractive = async () => {
    setError("");
    setBusy(true);
    try {
      const res = await api.startInteractiveLogin();
      if (res.authenticated) {
        setInteractiveWaiting(false);
        setBusy(false);
        onSuccess(res);
        onClose();
        return;
      }
      setBusy(false);
      setInteractiveWaiting(true);
    } catch (err) {
      setBusy(false);
      setInteractiveWaiting(false);
      setError(
        err instanceof ApiError
          ? err.message
          : "Could not open interactive login window."
      );
    }
  };

  const handleConnectExtension = async () => {
    setError("");
    setBusy(true);
    try {
      const found = await detectExtension(600);
      setExtDetected(found);
      if (!found) {
        setError(
          "LearnedLeague Analytics Bridge extension was not detected in this browser."
        );
        return;
      }
      const auth = await extCheckAuth();
      setExtensionAuth(auth);
      onSuccess(auth);
      onClose();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Failed connecting via Chrome extension."
      );
    } finally {
      setBusy(false);
    }
  };

  const modalTitle =
    mode === "desktop"
      ? "Sign In via LearnedLeague Browser Window"
      : "Connect Chrome Extension";

  return (
    <ModalDialog open={open} onClose={onClose} title={modalTitle}>
      <div className="space-y-4">
        <div
          className="flex items-start gap-2.5 p-3 rounded-lg text-sm ll-muted"
          style={{ color: "var(--text-secondary)" }}
        >
          <ShieldCheck
            className="w-5 h-5 text-emerald-600 dark:text-emerald-400 shrink-0 mt-0.5"
            aria-hidden="true"
          />
          <div>
            {mode === "desktop" ? (
              <span>
                Signs in directly inside a real{" "}
                <strong>learnedleague.com</strong> window on your Mac — no
                passwords or session cookies are shared or stored in plaintext.
              </span>
            ) : (
              <span>
                Uses your own logged-in Chrome session on{" "}
                <strong>learnedleague.com</strong> via the companion extension —
                no passwords or cookies ever leave your browser.
              </span>
            )}
          </div>
        </div>

        {mode === "desktop" ? (
          <div className="space-y-3">
            <p
              className="text-xs leading-relaxed"
              style={{ color: "var(--text-secondary)" }}
            >
              Opens a real browser window to{" "}
              <strong>learnedleague.com/ucp.php?mode=login</strong> on this
              computer. Complete any Cloudflare or CAPTCHA check and sign in
              inside that window; this dialog finishes automatically once you&apos;re
              signed in.
            </p>

            {interactiveWaiting && (
              <div className="ll-muted p-3 rounded-lg text-xs">
                Waiting for you to finish signing in inside the LearnedLeague
                window...
              </div>
            )}

            {error && (
              <p role="alert" className="text-sm text-red-600 dark:text-red-400">
                {error}
              </p>
            )}

            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={onClose}
                className="ll-muted px-4 min-h-10 rounded-lg text-sm font-medium cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => void handleStartInteractive()}
                className="inline-flex items-center gap-1.5 px-4 min-h-10 rounded-lg text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-60 cursor-pointer"
              >
                <Globe className="w-4 h-4" aria-hidden="true" />
                {busy
                  ? "Opening Window..."
                  : interactiveWaiting
                    ? "Show / Focus Login Window"
                    : "Open LearnedLeague Login Window"}
              </button>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            <div className="ll-muted p-3 rounded-lg text-xs space-y-1.5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span>
                  Extension status:{" "}
                  {extDetected === null ? (
                    <strong>Checking...</strong>
                  ) : extDetected ? (
                    <strong className="text-emerald-600 dark:text-emerald-400">
                      Detected and ready
                    </strong>
                  ) : (
                    <strong className="text-amber-600 dark:text-amber-400">
                      Not detected in this browser
                    </strong>
                  )}
                </span>
                <a
                  href="https://www.learnedleague.com/ucp.php?mode=login"
                  target="_blank"
                  rel="noreferrer"
                  className="text-blue-600 dark:text-blue-400 underline font-medium"
                >
                  Open learnedleague.com sign-in
                </a>
              </div>
              {extDetected === false && (
                <div style={{ color: "var(--text-secondary)" }}>
                  Load the <code>extension/</code> folder in Chrome via{" "}
                  <code>chrome://extensions</code> &rarr; enable{" "}
                  <strong>Developer mode</strong> &rarr;{" "}
                  <strong>Load unpacked</strong>, sign in at{" "}
                  <code>learnedleague.com</code>, then refresh this page.
                </div>
              )}
            </div>

            {error && (
              <p role="alert" className="text-sm text-red-600 dark:text-red-400">
                {error}
              </p>
            )}

            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={onClose}
                className="ll-muted px-4 min-h-10 rounded-lg text-sm font-medium cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => void handleConnectExtension()}
                className="inline-flex items-center gap-1.5 px-4 min-h-10 rounded-lg text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-60 cursor-pointer"
              >
                <Puzzle className="w-4 h-4" aria-hidden="true" />
                {busy ? "Connecting..." : "Connect via Chrome Extension"}
              </button>
            </div>
          </div>
        )}
      </div>
    </ModalDialog>
  );
}

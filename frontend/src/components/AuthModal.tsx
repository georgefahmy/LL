import { useEffect, useId, useState, type FormEvent } from "react";
import { Eye, EyeOff, Globe, KeyRound, Puzzle, ShieldCheck } from "lucide-react";

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
  keychainAvailable: boolean;
  onSuccess: (auth: AuthMe) => void;
}

export function AuthModal({
  open,
  onClose,
  mode,
  keychainAvailable,
  onSuccess,
}: AuthModalProps) {
  const [tab, setTab] = useState<"credentials" | "cookie" | "interactive" | "extension">(
    "credentials"
  );
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [cookieInput, setCookieInput] = useState("");
  const [rememberMe, setRememberMe] = useState(mode === "desktop" && keychainAvailable);
  const [busy, setBusy] = useState(false);
  const [interactiveWaiting, setInteractiveWaiting] = useState(false);
  const [extDetected, setExtDetected] = useState<boolean | null>(null);
  const [error, setError] = useState("");

  const credTabId = useId();
  const cookieTabId = useId();
  const interactiveTabId = useId();
  const extTabId = useId();

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setError("");
    if (mode === "desktop") {
      setTab("interactive");
    }
    setExtDetected(null);
    detectExtension(400).then((found) => {
      if (cancelled) return;
      setExtDetected(found);
      if (mode !== "desktop" && found) {
        setTab("extension");
      }
    });
    return () => {
      cancelled = true;
    };
  }, [open, mode]);

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

  useEffect(() => {
    if (!open || tab !== "interactive" || !interactiveWaiting) return;
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
  }, [open, tab, interactiveWaiting, onSuccess, onClose]);

  useEffect(() => {
    if (!open) {
      setInteractiveWaiting(false);
      setBusy(false);
    }
  }, [open]);

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

  const handleCredSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const auth = await api.login(username, password, rememberMe);
      setPassword("");
      onSuccess(auth);
      onClose();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Login failed.");
    } finally {
      setBusy(false);
    }
  };

  const handleCookieSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const auth = await api.loginWithCookie(cookieInput, rememberMe);
      setCookieInput("");
      onSuccess(auth);
      onClose();
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Cookie verification failed."
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <ModalDialog open={open} onClose={onClose} title="Sign In to LearnedLeague">
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
            {mode === "web" ? (
              <span>
                Your password is sent once directly to{" "}
                <strong>learnedleague.com</strong> and immediately discarded.
                Only your LL session cookies are stored in an encrypted{" "}
                <code>HttpOnly</code> cookie in your browser.
              </span>
            ) : (
              <span>
                Authenticates directly with <strong>learnedleague.com</strong>.
                Optional session saving uses your OS Keychain instead of
                plaintext files.
              </span>
            )}
          </div>
        </div>

        <div
          role="tablist"
          aria-label="Authentication methods"
          className="flex flex-wrap gap-3 border-b"
          style={{ borderColor: "var(--border-subtle)" }}
        >
          <button
            type="button"
            role="tab"
            id={credTabId}
            aria-selected={tab === "credentials"}
            onClick={() => {
              setTab("credentials");
              setInteractiveWaiting(false);
              setError("");
            }}
            className="ll-tab-btn pb-2.5 px-1 text-sm font-medium cursor-pointer"
          >
            LL Credentials
          </button>
          <button
            type="button"
            role="tab"
            id={cookieTabId}
            aria-selected={tab === "cookie"}
            onClick={() => {
              setTab("cookie");
              setInteractiveWaiting(false);
              setError("");
            }}
            className="ll-tab-btn pb-2.5 px-1 text-sm font-medium cursor-pointer"
          >
            Paste Session Cookie
          </button>
          <button
            type="button"
            role="tab"
            id={interactiveTabId}
            aria-selected={tab === "interactive"}
            onClick={() => {
              setTab("interactive");
              setError("");
            }}
            className="ll-tab-btn pb-2.5 px-1 text-sm font-medium cursor-pointer"
          >
            Interactive Browser
          </button>
          <button
            type="button"
            role="tab"
            id={extTabId}
            aria-selected={tab === "extension"}
            onClick={() => {
              setTab("extension");
              setInteractiveWaiting(false);
              setError("");
            }}
            className="ll-tab-btn pb-2.5 px-1 text-sm font-medium cursor-pointer"
          >
            Chrome Extension
          </button>
        </div>

        <div role="tabpanel" aria-labelledby={credTabId} hidden={tab !== "credentials"}>
          <form onSubmit={handleCredSubmit} className="space-y-3">
            <div>
              <label htmlFor="ll-username" className="block text-sm font-medium mb-1">
                LearnedLeague Username
              </label>
              <input
                id="ll-username"
                name="username"
                type="text"
                autoComplete="username"
                spellCheck={false}
                autoCapitalize="none"
                autoCorrect="off"
                enterKeyHint="next"
                required
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="ll-input w-full"
              />
            </div>

            <div>
              <label htmlFor="ll-password" className="block text-sm font-medium mb-1">
                Password
              </label>
              <div className="flex gap-2">
                <input
                  id="ll-password"
                  name="password"
                  type={showPassword ? "text" : "password"}
                  autoComplete="current-password"
                  enterKeyHint="done"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="ll-input w-full"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  className="ll-muted px-3 rounded-lg cursor-pointer shrink-0"
                >
                  {showPassword ? (
                    <EyeOff className="w-4 h-4" aria-hidden="true" />
                  ) : (
                    <Eye className="w-4 h-4" aria-hidden="true" />
                  )}
                </button>
              </div>
            </div>

            {mode === "desktop" && keychainAvailable && (
              <label className="flex items-center gap-2 text-sm cursor-pointer">
                <input
                  type="checkbox"
                  checked={rememberMe}
                  onChange={(e) => setRememberMe(e.target.checked)}
                />
                Remember session securely in OS Keychain
              </label>
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
                type="submit"
                disabled={busy}
                className="px-4 min-h-10 rounded-lg text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-60 cursor-pointer"
              >
                {busy ? "Signing In..." : "Sign In to LearnedLeague"}
              </button>
            </div>
          </form>
        </div>

        <div role="tabpanel" aria-labelledby={cookieTabId} hidden={tab !== "cookie"}>
          <form onSubmit={handleCookieSubmit} className="space-y-3">
            <p className="text-xs leading-relaxed" style={{ color: "var(--text-secondary)" }}>
              Sign in at{" "}
              <a
                href="https://www.learnedleague.com"
                target="_blank"
                rel="noreferrer"
                className="text-blue-600 dark:text-blue-400 underline"
              >
                learnedleague.com
              </a>
              , open Browser DevTools &rarr; Network &rarr; copy the{" "}
              <code>Cookie</code> request header (e.g.{" "}
              <code>phpbb3_..._sid=...; phpbb3_..._u=...</code>), and paste below.
            </p>
            <div>
              <label htmlFor="ll-cookie-str" className="block text-sm font-medium mb-1">
                Cookie Header String
              </label>
              <textarea
                id="ll-cookie-str"
                name="cookie"
                rows={3}
                required
                spellCheck={false}
                value={cookieInput}
                onChange={(e) => setCookieInput(e.target.value)}
                className="ll-input w-full font-mono text-xs"
              />
            </div>

            {mode === "desktop" && keychainAvailable && (
              <label className="flex items-center gap-2 text-sm cursor-pointer">
                <input
                  type="checkbox"
                  checked={rememberMe}
                  onChange={(e) => setRememberMe(e.target.checked)}
                />
                Remember session securely in OS Keychain
              </label>
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
                type="submit"
                disabled={busy}
                className="inline-flex items-center gap-1.5 px-4 min-h-10 rounded-lg text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-60 cursor-pointer"
              >
                <KeyRound className="w-4 h-4" aria-hidden="true" />
                {busy ? "Verifying..." : "Verify Session Cookie"}
              </button>
            </div>
          </form>
        </div>

        <div
          role="tabpanel"
          aria-labelledby={interactiveTabId}
          hidden={tab !== "interactive"}
        >
          <div className="space-y-3">
            <p className="text-xs leading-relaxed" style={{ color: "var(--text-secondary)" }}>
              Opens a real browser window to{" "}
              <strong>learnedleague.com/ucp.php?mode=login</strong> on this computer.
              Complete any Cloudflare or CAPTCHA check and sign in inside that window;
              this dialog will finish automatically once you&apos;re signed in.
            </p>

            {tab === "interactive" && interactiveWaiting && (
              <div className="ll-muted p-3 rounded-lg text-xs">
                Waiting for you to finish signing in inside the LearnedLeague window...
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
        </div>

        <div
          role="tabpanel"
          aria-labelledby={extTabId}
          hidden={tab !== "extension"}
        >
          <div className="space-y-3">
            <p className="text-xs leading-relaxed" style={{ color: "var(--text-secondary)" }}>
              Use your own logged-in Chrome session on{" "}
              <strong>learnedleague.com</strong> via the companion{" "}
              <strong>LearnedLeague Analytics Bridge</strong> extension — no passwords or
              cookies ever leave your browser.
            </p>

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
                  <strong>Developer mode</strong> &rarr; <strong>Load unpacked</strong>,
                  sign in at <code>learnedleague.com</code>, then refresh this page.
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
        </div>
      </div>
    </ModalDialog>
  );
}

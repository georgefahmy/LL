import { useState, type FormEvent } from "react";
import { Lock } from "lucide-react";

import { api, ApiError } from "../api/client";

interface AccessGateProps {
  onUnlocked: () => void;
}

export function AccessGate({ onUnlocked }: AccessGateProps) {
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await api.verifyGate(code);
      onUnlocked();
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Failed to verify access code."
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="min-h-screen flex items-center justify-center p-4">
      <div className="ll-card w-full max-w-md p-6 shadow-xl space-y-4">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-blue-600/15 text-blue-600 dark:text-blue-400">
            <Lock className="w-6 h-6" aria-hidden="true" />
          </div>
          <div>
            <h1 className="text-xl font-bold m-0">LearnedLeague Tool</h1>
            <p className="text-sm m-0" style={{ color: "var(--text-secondary)" }}>
              Enter the shared access code to continue.
            </p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-3">
          <div>
            <label htmlFor="ll-access-code" className="block text-sm font-medium mb-1">
              Access Code
            </label>
            <input
              id="ll-access-code"
              name="access_code"
              type="password"
              required
              autoFocus
              value={code}
              onChange={(e) => setCode(e.target.value)}
              className="ll-input w-full"
            />
          </div>
          {error && (
            <p role="alert" className="text-sm text-red-600 dark:text-red-400">
              {error}
            </p>
          )}
          <button
            type="submit"
            disabled={busy}
            className="w-full min-h-10 rounded-lg font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-60 cursor-pointer"
          >
            {busy ? "Verifying..." : "Unlock App"}
          </button>
        </form>
      </div>
    </main>
  );
}

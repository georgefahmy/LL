import { useRef, useState } from "react";
import { Download, RefreshCw, ShieldAlert, Upload } from "lucide-react";

import { api } from "../api/client";
import { isExtensionAuthActive } from "../api/extensionBridge";
import type { LocalStore } from "../storage/localStore";
import type { AppMeta, PersonalDataExport } from "../types";

export type ColorSchemePref = "system" | "light" | "dark";

interface SettingsPageProps {
  meta: AppMeta;
  colorScheme: ColorSchemePref;
  onChangeColorScheme: (pref: ColorSchemePref) => void;
  localStore: LocalStore;
  onRefreshMeta: () => Promise<void>;
}

export function SettingsPage({
  meta,
  colorScheme,
  onChangeColorScheme,
  localStore,
  onRefreshMeta,
}: SettingsPageProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [statusMsg, setStatusMsg] = useState("");
  const [busy, setBusy] = useState(false);

  const handleSyncNow = async () => {
    setBusy(true);
    setStatusMsg("");
    try {
      if (isExtensionAuthActive()) {
        const summary = await api.syncArchiveViaExtension((msg) =>
          setStatusMsg(msg)
        );
        await onRefreshMeta();
        if (summary.syncedDays === 0) {
          setStatusMsg(
            `Archive is up to date through LL ${summary.latestSeason} MD ${summary.currentDay}.`
          );
        } else {
          const remText =
            summary.remainingDays > 0
              ? ` (${summary.remainingDays} older match days remaining — click Sync again for the next batch.)`
              : "";
          setStatusMsg(
            `Synced ${summary.syncedDays} match days (${summary.importedQuestions} questions) via Chrome Extension.${remText}`
          );
        }
        return;
      }
      const res = await api.triggerSync();
      setStatusMsg(
        res.triggered
          ? "Background archive sync started."
          : "Background sync is already running."
      );
      await onRefreshMeta();
    } catch (err) {
      setStatusMsg(err instanceof Error ? err.message : "Failed triggering sync.");
    } finally {
      setBusy(false);
    }
  };

  const handleExport = async () => {
    const data = await localStore.exportAll();
    const blob = new Blob([JSON.stringify(data, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `learnedleague_backup_${new Date().toISOString().slice(0, 10)}.json`;
    link.click();
    URL.revokeObjectURL(url);
    setStatusMsg("Exported personal practice history and favorites.");
  };

  const handleImport = async (file: File | undefined) => {
    if (!file) return;
    try {
      const text = await file.text();
      const parsed = JSON.parse(text) as PersonalDataExport;
      await localStore.importAll(parsed);
      setStatusMsg("Imported personal backup data successfully.");
    } catch {
      setStatusMsg("Failed importing JSON backup — verify file format.");
    }
  };

  const handleDeleteLegacyLogin = async () => {
    const res = await api.deleteLegacyLoginFile();
    await onRefreshMeta();
    setStatusMsg(
      res.deleted
        ? "Removed legacy plaintext ~/.LearnedLeague/login_info.json."
        : "Legacy login file was already absent."
    );
  };

  return (
    <div className="space-y-4 max-w-3xl">
      <h1 className="text-xl font-bold m-0">Settings &amp; Archive</h1>

      {/* Appearance */}
      <section className="ll-card p-5 space-y-3">
        <h2 className="text-base font-semibold m-0">Appearance</h2>
        <p className="text-xs m-0" style={{ color: "var(--text-secondary)" }}>
          Follows your operating system color scheme by default, or pin light or
          dark theme explicitly.
        </p>
        <div className="flex flex-wrap gap-2" role="radiogroup" aria-label="Theme preference">
          {(
            [
              ["system", "System Default"],
              ["light", "Light"],
              ["dark", "Dark"],
            ] as const
          ).map(([val, label]) => (
            <button
              key={val}
              type="button"
              role="radio"
              aria-checked={colorScheme === val}
              onClick={() => onChangeColorScheme(val)}
              className={`px-3.5 min-h-9 rounded-lg text-sm font-medium cursor-pointer ${
                colorScheme === val
                  ? "bg-blue-600 text-white"
                  : "ll-muted"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </section>

      {/* Question Archive Sync */}
      <section className="ll-card p-5 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-base font-semibold m-0">Question Archive</h2>
          <button
            type="button"
            disabled={busy || meta.sync_status.running}
            onClick={() => void handleSyncNow()}
            className="px-3.5 min-h-9 rounded-lg text-xs font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50 inline-flex items-center gap-1.5 cursor-pointer"
          >
            <RefreshCw className="w-3.5 h-3.5" aria-hidden="true" />
            {busy || meta.sync_status.running ? "Syncing..." : "Sync New Match Days"}
          </button>
        </div>

        <dl className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-sm m-0">
          <div className="ll-muted p-3 rounded-lg">
            <dt className="text-xs" style={{ color: "var(--text-secondary)" }}>
              Cached Questions
            </dt>
            <dd className="text-lg font-mono font-bold m-0">
              {meta.question_count.toLocaleString()}
            </dd>
          </div>
          <div className="ll-muted p-3 rounded-lg">
            <dt className="text-xs" style={{ color: "var(--text-secondary)" }}>
              Latest Season / Day
            </dt>
            <dd className="text-lg font-mono font-bold m-0">
              LL {meta.latest_season} &bull; MD {meta.current_day}
            </dd>
          </div>
          <div className="ll-muted p-3 rounded-lg">
            <dt className="text-xs" style={{ color: "var(--text-secondary)" }}>
              Sync Status
            </dt>
            <dd className="text-sm font-medium m-0 mt-1">
              {meta.sync_status.running
                ? `${meta.sync_status.completed_days}/${meta.sync_status.total_missing_days} days`
                : busy
                  ? "syncing (extension)"
                  : meta.sync_status.phase}
            </dd>
          </div>
        </dl>

        {!busy && meta.sync_status.last_error && (
          <p className="text-xs text-rose-600 dark:text-rose-400 m-0">
            Last sync error: {meta.sync_status.last_error}
          </p>
        )}
      </section>

      {/* Personal Data Backup */}
      <section className="ll-card p-5 space-y-3">
        <h2 className="text-base font-semibold m-0">
          Personal Data ({meta.mode === "desktop" ? "Local SQLite" : "Browser Storage"})
        </h2>
        <p className="text-xs m-0" style={{ color: "var(--text-secondary)" }}>
          {meta.mode === "web"
            ? "Your practice answers, completed OneDays, and favorite players are stored privately inside this browser. Export a JSON backup to transfer to another device."
            : "Your practice answers, completed OneDays, and favorite players are saved locally inside ~/.LearnedLeague/app.db."}
        </p>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => void handleExport()}
            className="ll-muted px-3.5 min-h-9 rounded-lg text-sm font-medium inline-flex items-center gap-1.5 cursor-pointer"
          >
            <Download className="w-4 h-4" aria-hidden="true" />
            Export Backup JSON
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept="application/json,.json"
            className="hidden"
            onChange={(e) => void handleImport(e.target.files?.[0])}
          />
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            className="ll-muted px-3.5 min-h-9 rounded-lg text-sm font-medium inline-flex items-center gap-1.5 cursor-pointer"
          >
            <Upload className="w-4 h-4" aria-hidden="true" />
            Import Backup JSON
          </button>
        </div>
      </section>

      {/* Legacy Plaintext File Warning (Desktop only) */}
      {meta.mode === "desktop" && meta.has_legacy_login_file && (
        <section className="ll-card p-5 border-amber-500/50 bg-amber-500/10 space-y-2.5">
          <div className="flex items-center gap-2 font-semibold text-sm">
            <ShieldAlert className="w-4 h-4 text-amber-600" aria-hidden="true" />
            Legacy Plaintext Login File Detected
          </div>
          <p className="text-xs m-0">
            Older versions stored your LearnedLeague password in plaintext at{" "}
            <code>~/.LearnedLeague/login_info.json</code>. v9.0 uses your OS Keychain
            instead — you can safely delete the old plaintext file now.
          </p>
          <button
            type="button"
            onClick={() => void handleDeleteLegacyLogin()}
            className="px-3.5 min-h-9 rounded-lg text-xs font-medium text-white bg-amber-600 hover:bg-amber-700 cursor-pointer"
          >
            Delete Legacy login_info.json
          </button>
        </section>
      )}

      {statusMsg && (
        <p role="status" className="text-sm font-medium text-emerald-700 dark:text-emerald-300">
          {statusMsg}
        </p>
      )}
    </div>
  );
}

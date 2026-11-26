import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ArrowUpCircle,
  ExternalLink,
  Lock,
  LogIn,
  LogOut,
  Moon,
  Puzzle,
  RefreshCw,
  Settings as SettingsIcon,
  Sun,
} from "lucide-react";

import { api, setAuthEventHandler } from "./api/client";
import {
  detectExtension,
  disconnectExtension,
  extCheckAuth,
  isExtensionAuthActive,
  isExtensionManuallyDisconnected,
  setExtensionAuth,
} from "./api/extensionBridge";
import { AccessGate } from "./components/AccessGate";
import { AuthModal } from "./components/AuthModal";
import { DefensePage } from "./pages/DefensePage";
import { HistoryPage } from "./pages/HistoryPage";
import { LuckPage } from "./pages/LuckPage";
import { MiniLeaguesPage } from "./pages/MiniLeaguesPage";
import { MockDayPage } from "./pages/MockDayPage";
import { OneDaysPage } from "./pages/OneDaysPage";
import { PracticePage } from "./pages/PracticePage";
import { SettingsPage, type ColorSchemePref } from "./pages/SettingsPage";
import { StatsPage } from "./pages/StatsPage";
import { createLocalStore } from "./storage/localStore";
import type { AppMeta, AuthMe } from "./types";

type PageId =
  | "practice"
  | "onedays"
  | "minileagues"
  | "mockday"
  | "stats"
  | "defense"
  | "luck"
  | "history"
  | "settings";

const NAV_ITEMS: { id: PageId; label: string; requiresAuth: boolean }[] = [
  { id: "practice", label: "Practice", requiresAuth: false },
  { id: "onedays", label: "OneDays", requiresAuth: false },
  { id: "minileagues", label: "Mini Leagues", requiresAuth: false },
  { id: "mockday", label: "Mock Day", requiresAuth: false },
  { id: "stats", label: "Stats", requiresAuth: true },
  { id: "defense", label: "Defense", requiresAuth: false },
  { id: "luck", label: "Luck", requiresAuth: true },
  { id: "history", label: "History", requiresAuth: true },
  { id: "settings", label: "Settings", requiresAuth: false },
];

const WEB_NAV_IDS: ReadonlySet<PageId> = new Set([
  "stats",
  "defense",
  "luck",
  "history",
  "settings",
]);

const COLOR_SCHEME_STORAGE_KEY = "ll-color-scheme";

function readStoredScheme(): ColorSchemePref {
  try {
    const val = localStorage.getItem(COLOR_SCHEME_STORAGE_KEY);
    if (val === "light" || val === "dark") return val;
  } catch {
    // Ignore storage errors
  }
  return "system";
}

function applyMetaScheme(pref: ColorSchemePref): void {
  const meta = document.querySelector('meta[name="color-scheme"]');
  if (meta) {
    meta.setAttribute("content", pref === "system" ? "light dark" : pref);
  }
}

export function App() {
  const [meta, setMeta] = useState<AppMeta | null>(null);
  const [auth, setAuth] = useState<AuthMe>({
    authenticated: false,
    username: null,
    formatted_username: null,
    profile_id: null,
    desktop_keychain_available: false,
    has_saved_keychain_session: false,
    has_legacy_login_file: false,
  });
  const [activePage, setActivePage] = useState<PageId>("practice");
  const [authModalOpen, setAuthModalOpen] = useState(false);
  const [extDetected, setExtDetected] = useState(false);
  const [authSource, setAuthSource] = useState<"server" | "extension" | null>(null);
  const [connectingExt, setConnectingExt] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [colorScheme, setColorScheme] = useState<ColorSchemePref>(readStoredScheme);
  const [systemDark, setSystemDark] = useState<boolean>(() =>
    typeof window !== "undefined"
      ? window.matchMedia("(prefers-color-scheme: dark)").matches
      : false
  );

  const localStore = useMemo(
    () => createLocalStore(meta?.mode ?? "web"),
    [meta?.mode]
  );

  const visibleNavItems = useMemo(
    () =>
      meta?.mode === "web"
        ? NAV_ITEMS.filter((it) => WEB_NAV_IDS.has(it.id))
        : NAV_ITEMS,
    [meta?.mode]
  );

  const updateColorScheme = useCallback((pref: ColorSchemePref) => {
    setColorScheme(pref);
    applyMetaScheme(pref);
    try {
      if (pref === "system") {
        localStorage.removeItem(COLOR_SCHEME_STORAGE_KEY);
      } else {
        localStorage.setItem(COLOR_SCHEME_STORAGE_KEY, pref);
      }
    } catch {
      // Ignore storage errors
    }
  }, []);

  const handleQuickSchemeToggle = () => {
    const renderedDark =
      colorScheme === "dark" || (colorScheme === "system" && systemDark);
    const target: "light" | "dark" = renderedDark ? "light" : "dark";
    const matchesSystem = (target === "dark") === systemDark;
    updateColorScheme(matchesSystem ? "system" : target);
  };

  useEffect(() => {
    applyMetaScheme(colorScheme);
  }, [colorScheme]);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onMqChange = (e: MediaQueryListEvent) => setSystemDark(e.matches);
    mq.addEventListener("change", onMqChange);

    const onStorage = (e: StorageEvent) => {
      if (e.key === COLOR_SCHEME_STORAGE_KEY) {
        const next =
          e.newValue === "light" || e.newValue === "dark" ? e.newValue : "system";
        setColorScheme(next);
        applyMetaScheme(next);
      }
    };
    window.addEventListener("storage", onStorage);
    return () => {
      mq.removeEventListener("change", onMqChange);
      window.removeEventListener("storage", onStorage);
    };
  }, []);

  useEffect(() => {
    const label = NAV_ITEMS.find((it) => it.id === activePage)?.label ?? "Defense";
    const appTitle =
      meta?.mode === "web"
        ? "LearnedLeague Analytics"
        : "LearnedLeague Practice Tool";
    document.title = `${label} | ${appTitle}`;
  }, [activePage, meta?.mode]);

  const refreshMetaAndAuth = useCallback(async () => {
    try {
      const m = await api.getMeta();
      setMeta(m);
      if (m.mode === "web") {
        setActivePage((prev) => (WEB_NAV_IDS.has(prev) ? prev : "defense"));
      }
      const hasExt = m.mode === "web" ? await detectExtension(500) : false;
      setExtDetected(hasExt);
      if (!m.access_gate_required || m.access_gate_unlocked) {
        let me = await api.getAuthMe();
        if (
          m.mode === "desktop" &&
          !me.authenticated &&
          me.has_saved_keychain_session
        ) {
          const autoRes = await api.autoLogin();
          if (autoRes.authenticated) {
            me = await api.getAuthMe();
          }
        }
        if (me.authenticated) {
          setAuth(me);
          setAuthSource("server");
        } else if (m.mode === "web" && hasExt && !isExtensionManuallyDisconnected()) {
          try {
            const extMe = await extCheckAuth();
            setExtensionAuth(extMe);
            setAuth(extMe);
            setAuthSource("extension");
          } catch {
            setAuth(me);
            setAuthSource(null);
          }
        } else {
          setAuth(me);
          setAuthSource(null);
        }
      }
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : "Unable to contact backend.");
    }
  }, []);

  useEffect(() => {
    void refreshMetaAndAuth();
  }, [refreshMetaAndAuth]);

  useEffect(() => {
    setAuthEventHandler((code) => {
      if (code === "LL_AUTH_REQUIRED") {
        setExtensionAuth(null);
        setAuthSource(null);
        setAuth((prev) => ({ ...prev, authenticated: false }));
        setAuthModalOpen(true);
      } else if (code === "ACCESS_GATE_REQUIRED") {
        setMeta((prev) => (prev ? { ...prev, access_gate_unlocked: false } : prev));
      }
    });
    return () => setAuthEventHandler(null);
  }, []);

  // Poll background sync while running
  useEffect(() => {
    if (!meta?.sync_status.running) return;
    const timer = window.setInterval(() => {
      api
        .getMeta()
        .then(setMeta)
        .catch(() => {});
    }, 3000);
    return () => window.clearInterval(timer);
  }, [meta?.sync_status.running]);

  // Refresh live latest_season and current_day once authenticated
  useEffect(() => {
    if (!auth.authenticated) return;
    let cancelled = false;
    api
      .getLatestSeason()
      .then((info) => {
        if (cancelled) return;
        setMeta((prev) =>
          prev
            ? {
                ...prev,
                latest_season: info.latest_season,
                current_day: info.current_day,
              }
            : prev
        );
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [auth.authenticated]);

  const handleQuickConnectExtension = async () => {
    setConnectingExt(true);
    try {
      const extMe = await extCheckAuth();
      setExtensionAuth(extMe);
      setAuth(extMe);
      setAuthSource("extension");
    } catch {
      setAuthModalOpen(true);
    } finally {
      setConnectingExt(false);
    }
  };

  const handleLogout = async () => {
    disconnectExtension();
    setAuthSource(null);
    await api.logout(true);
    setAuth((prev) => ({
      ...prev,
      authenticated: false,
      username: null,
      formatted_username: null,
      profile_id: null,
      has_saved_keychain_session: false,
    }));
  };

  if (loadError) {
    return (
      <main className="min-h-screen flex items-center justify-center p-4">
        <div className="ll-card p-6 max-w-md space-y-3 text-center">
          <h1 className="text-lg font-bold m-0">Startup Error</h1>
          <p className="text-sm text-rose-600 dark:text-rose-400 m-0">{loadError}</p>
          <button
            type="button"
            onClick={() => {
              setLoadError("");
              void refreshMetaAndAuth();
            }}
            className="px-4 min-h-9 rounded-lg text-sm font-medium text-white bg-blue-600 cursor-pointer"
          >
            Retry
          </button>
        </div>
      </main>
    );
  }

  if (!meta) {
    return (
      <main className="min-h-screen flex items-center justify-center p-4 text-sm">
        Loading LearnedLeague Practice Tool...
      </main>
    );
  }

  if (meta.access_gate_required && !meta.access_gate_unlocked) {
    return <AccessGate onUnlocked={() => void refreshMetaAndAuth()} />;
  }

  const renderedDark =
    colorScheme === "dark" || (colorScheme === "system" && systemDark);

  return (
    <div className="min-h-screen flex flex-col">
      <header
        className="sticky top-0 z-20 border-b backdrop-blur-sm"
        style={{
          backgroundColor: "var(--bg-card)",
          borderColor: "var(--border-subtle)",
        }}
      >
        <div className="max-w-[1680px] mx-auto px-4 py-2.5 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <img src="/ll_logo.png" alt="" className="w-8 h-8 rounded-lg" />
            <div>
              <div className="font-bold text-sm leading-tight">
                {meta.mode === "web"
                  ? "LearnedLeague Analytics"
                  : "LearnedLeague Practice Tool"}
              </div>
              <div className="text-xs flex items-center gap-2" style={{ color: "var(--text-secondary)" }}>
                {meta.mode === "web" ? (
                  <span>
                    Extension Edition v{meta.extension_version ?? meta.version}
                  </span>
                ) : (
                  <>
                    <span>v{meta.version}</span>
                    <span>&bull;</span>
                    <span>{meta.question_count.toLocaleString()} Qs</span>
                    {meta.sync_status.running && (
                      <span className="inline-flex items-center gap-1 text-blue-600 dark:text-blue-400">
                        <RefreshCw className="w-3 h-3 animate-spin" aria-hidden="true" />
                        Syncing {meta.sync_status.completed_days}/
                        {meta.sync_status.total_missing_days}
                      </span>
                    )}
                  </>
                )}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <a
              href="https://www.learnedleague.com"
              target="_blank"
              rel="noreferrer"
              className="ll-muted px-2.5 min-h-8 rounded-lg text-xs font-medium inline-flex items-center gap-1"
            >
              LL.com
              <ExternalLink className="w-3 h-3" aria-hidden="true" />
            </a>

            <button
              type="button"
              onClick={handleQuickSchemeToggle}
              aria-label={
                renderedDark ? "Switch to light theme" : "Switch to dark theme"
              }
              title={renderedDark ? "Switch to light theme" : "Switch to dark theme"}
              className="ll-muted min-w-8 min-h-8 px-2 rounded-lg inline-flex items-center justify-center cursor-pointer"
            >
              {renderedDark ? (
                <Sun className="w-4 h-4" aria-hidden="true" />
              ) : (
                <Moon className="w-4 h-4" aria-hidden="true" />
              )}
            </button>

            {auth.authenticated ? (
              <div className="flex items-center gap-2">
                <span
                  title={
                    authSource === "extension"
                      ? "Connected via Chrome Extension"
                      : "Signed in"
                  }
                  className="text-xs font-semibold px-2.5 py-1 rounded-full bg-emerald-600/15 text-emerald-700 dark:text-emerald-300 inline-flex items-center gap-1.5"
                >
                  {authSource === "extension" && (
                    <Puzzle className="w-3 h-3" aria-hidden="true" />
                  )}
                  <span>{auth.formatted_username || auth.username}</span>
                </span>
                <button
                  type="button"
                  title={
                    authSource === "extension"
                      ? "Disconnect Chrome Extension (keeps learnedleague.com signed in)"
                      : "Sign out"
                  }
                  onClick={() => void handleLogout()}
                  className="ll-muted px-2.5 min-h-8 rounded-lg text-xs font-medium inline-flex items-center gap-1 cursor-pointer"
                >
                  <LogOut className="w-3.5 h-3.5" aria-hidden="true" />
                  {authSource === "extension" ? "Disconnect" : "Logout"}
                </button>
              </div>
            ) : (
              <div className="flex items-center gap-2">
                {extDetected && (
                  <button
                    type="button"
                    disabled={connectingExt}
                    onClick={() => void handleQuickConnectExtension()}
                    className="px-3 min-h-8 rounded-lg text-xs font-medium text-white bg-emerald-600 hover:bg-emerald-700 disabled:opacity-60 inline-flex items-center gap-1.5 cursor-pointer"
                  >
                    <Puzzle className="w-3.5 h-3.5" aria-hidden="true" />
                    {connectingExt ? "Connecting..." : "Connect Extension"}
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => setAuthModalOpen(true)}
                  className="px-3 min-h-8 rounded-lg text-xs font-medium text-white bg-blue-600 hover:bg-blue-700 inline-flex items-center gap-1.5 cursor-pointer"
                >
                  <LogIn className="w-3.5 h-3.5" aria-hidden="true" />
                  LL Login
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Primary Navigation */}
        <nav
          aria-label="Primary"
          className="max-w-[1680px] mx-auto px-4 flex items-center gap-1 overflow-x-auto pb-2"
        >
          {visibleNavItems.map((item) => {
            const active = activePage === item.id;
            const locked = item.requiresAuth && !auth.authenticated;
            return (
              <button
                key={item.id}
                type="button"
                aria-current={active ? "page" : undefined}
                onClick={() => setActivePage(item.id)}
                className={`min-h-9 px-3 rounded-lg text-xs sm:text-sm font-medium whitespace-nowrap inline-flex items-center gap-1.5 cursor-pointer transition-colors ${
                  active
                    ? "bg-blue-600 text-white"
                    : "hover:bg-slate-500/10"
                }`}
              >
                {item.id === "settings" && (
                  <SettingsIcon className="w-3.5 h-3.5" aria-hidden="true" />
                )}
                <span>{item.label}</span>
                {locked && <Lock className="w-3 h-3 opacity-70" aria-hidden="true" />}
              </button>
            );
          })}
        </nav>

        {/* Safe Desktop Update Banner */}
        {meta.mode === "desktop" && meta.update.update_available && (
          <div className="bg-blue-600 text-white text-xs px-4 py-1.5 flex items-center justify-center gap-2">
            <ArrowUpCircle className="w-4 h-4 shrink-0" aria-hidden="true" />
            <span>
              Update available: <strong>v{meta.update.latest_version}</strong>{" "}
              (currently v{meta.update.current_version})
            </span>
            <a
              href={meta.update.release_url}
              target="_blank"
              rel="noreferrer"
              className="underline font-semibold"
            >
              Download from GitHub Releases
            </a>
          </div>
        )}
      </header>

      <main className="flex-1 max-w-[1680px] w-full mx-auto p-4 md:p-6">
        {meta.mode === "desktop" && activePage === "practice" && (
          <PracticePage categories={meta.categories} localStore={localStore} />
        )}
        {meta.mode === "desktop" && activePage === "onedays" && (
          <OneDaysPage modkosUrl={meta.modkos_url} localStore={localStore} />
        )}
        {meta.mode === "desktop" && activePage === "minileagues" && (
          <MiniLeaguesPage />
        )}
        {meta.mode === "desktop" && activePage === "mockday" && (
          <MockDayPage localStore={localStore} />
        )}
        {activePage === "stats" && (
          <StatsPage
            auth={auth}
            statsDefinition={meta.stats_definition}
            localStore={localStore}
            onRequireLogin={() => setAuthModalOpen(true)}
          />
        )}
        {activePage === "defense" && (
          <DefensePage
            auth={auth}
            categories={meta.categories}
            latestSeason={meta.latest_season}
            currentDay={meta.current_day}
            onRequireLogin={() => setAuthModalOpen(true)}
          />
        )}
        {activePage === "luck" && (
          <LuckPage
            auth={auth}
            latestSeason={meta.latest_season}
            luckFields={meta.luck_fields}
            localStore={localStore}
            onRequireLogin={() => setAuthModalOpen(true)}
          />
        )}
        {activePage === "history" && (
          <HistoryPage
            auth={auth}
            categories={meta.categories}
            onRequireLogin={() => setAuthModalOpen(true)}
          />
        )}
        {activePage === "settings" && (
          <SettingsPage
            meta={meta}
            colorScheme={colorScheme}
            onChangeColorScheme={updateColorScheme}
            localStore={localStore}
            onRefreshMeta={refreshMetaAndAuth}
          />
        )}
      </main>

      <AuthModal
        open={authModalOpen}
        onClose={() => setAuthModalOpen(false)}
        mode={meta.mode}
        onSuccess={(nextAuth) => {
          setAuth((prev) => ({ ...prev, ...nextAuth, authenticated: true }));
          setAuthSource(isExtensionAuthActive() ? "extension" : "server");
        }}
      />
    </div>
  );
}

export default App;

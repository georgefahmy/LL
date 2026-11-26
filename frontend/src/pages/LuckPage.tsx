import { useEffect, useMemo, useState, type FormEvent } from "react";
import { AlertTriangle, Sparkles, Star, TrendingUp } from "lucide-react";

import { api } from "../api/client";
import { DataTable, type TableColumn } from "../components/DataTable";
import type { LocalStore } from "../storage/localStore";
import type { AuthMe, LuckAnalysisResponse } from "../types";

interface LuckPageProps {
  auth: AuthMe;
  latestSeason: number;
  luckFields: string[];
  localStore: LocalStore;
  onRequireLogin: () => void;
}

export function LuckPage({
  auth,
  latestSeason,
  luckFields,
  localStore,
  onRequireLogin,
}: LuckPageProps) {
  const [season, setSeason] = useState(latestSeason || 100);
  const [maxSeason, setMaxSeason] = useState(latestSeason || 100);
  const [usernamesText, setUsernamesText] = useState("");
  const [opponents, setOpponents] = useState<string[]>([]);
  const [selectedOpps, setSelectedOpps] = useState<string[]>([]);
  const [selectedFields, setSelectedFields] = useState<string[]>([]);
  const [rundleFlag, setRundleFlag] = useState(false);
  const [useSos, setUseSos] = useState(false);
  const [forceRefresh, setForceRefresh] = useState(false);
  const [divideNum, setDivideNum] = useState("TMP");
  const [divideDen, setDivideDen] = useState("TCA");
  const [dividePairs, setDividePairs] = useState<[string, string][]>([]);
  const [favorites, setFavorites] = useState<string[]>([]);
  const [highlightFavs, setHighlightFavs] = useState(true);

  const [result, setResult] = useState<LuckAnalysisResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!latestSeason) return;
    setMaxSeason((prev) => Math.max(prev, latestSeason));
    setSeason((prev) => (latestSeason > prev ? latestSeason : prev));
  }, [latestSeason]);

  useEffect(() => {
    localStore.getFavorites().then(setFavorites);
  }, [localStore]);

  useEffect(() => {
    if (!auth.authenticated) return;
    let cancelled = false;
    api
      .getLatestSeason()
      .then((res) => {
        if (cancelled || !res.latest_season) return;
        setMaxSeason((prev) => Math.max(prev, res.latest_season));
        setSeason((prev) =>
          res.latest_season > prev ? res.latest_season : prev
        );
      })
      .catch(() => {});

    api
      .getMyProfile()
      .then((me) => {
        if (cancelled) return;
        setOpponents([me.formatted_username, ...Object.keys(me.opponents)]);
        const pastNums = Object.keys(me.past_seasons || {})
          .map((k) => {
            const match = k.match(/(\d+)/);
            return match ? Number(match[1]) : 0;
          })
          .filter((n) => n >= 60);
        if (pastNums.length > 0) {
          const bestPast = Math.max(...pastNums);
          setMaxSeason((prev) => Math.max(prev, bestPast));
          setSeason((prev) => (bestPast > prev ? bestPast : prev));
        }
      })
      .catch(() => {});

    return () => {
      cancelled = true;
    };
  }, [auth.authenticated]);

  const seasonOptions = useMemo(() => {
    const maxS = Math.max(60, latestSeason || 0, maxSeason || 0);
    return Array.from({ length: maxS - 60 + 1 }, (_, i) => maxS - i);
  }, [latestSeason, maxSeason]);

  const handleLoadFavorites = async () => {
    const favs = await localStore.getFavorites();
    setFavorites(favs);
    if (favs.length > 0) {
      setUsernamesText(favs.join(" "));
    }
  };

  const handleSaveFavorites = async () => {
    const parsed = usernamesText
      .split(/[\s,]+/)
      .map((s) => s.trim())
      .filter(Boolean);
    const merged = Array.from(new Set([...favorites, ...parsed, ...selectedOpps]));
    setFavorites(await localStore.setFavorites(merged));
  };

  const handleAnalyze = async (e: FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const typed = usernamesText
        .split(/[\s,]+/)
        .map((s) => s.trim())
        .filter(Boolean);
      const users = typed.length > 0 ? typed : selectedOpps;
      const res = await api.analyzeLuck({
        season,
        usernames: users,
        extra_fields: selectedFields,
        rundle_flag: rundleFlag,
        use_sos: useSos,
        divide_pairs: dividePairs,
        refresh: forceRefresh,
      });
      setResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Luck analysis failed.");
    } finally {
      setLoading(false);
    }
  };

  if (!auth.authenticated) {
    return (
      <div className="ll-card p-8 text-center space-y-3">
        <TrendingUp className="w-8 h-8 mx-auto opacity-60" aria-hidden="true" />
        <h1 className="text-lg font-semibold m-0">LearnedLeague Login Required</h1>
        <p className="text-sm m-0" style={{ color: "var(--text-secondary)" }}>
          Sign in with your LearnedLeague account to run OLS Luck Analysis on
          league-wide standings.
        </p>
        <button
          type="button"
          onClick={onRequireLogin}
          className="px-4 min-h-10 rounded-lg text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 cursor-pointer"
        >
          Sign In to LearnedLeague
        </button>
      </div>
    );
  }

  const textCols = new Set(["Player", "Rundle", "League", "Branch", "Level"]);
  const columns: TableColumn<Record<string, unknown>>[] = (result?.columns ?? []).map(
    (col) => ({
      key: col,
      label: col,
      type: textCols.has(col) ? "text" : "number",
    })
  );

  return (
    <div className="space-y-4">
      <form onSubmit={handleAnalyze} className="ll-card p-4 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h1 className="text-lg font-semibold m-0">Luck Analysis (OLS Regression)</h1>
            <p className="text-xs m-0" style={{ color: "var(--text-secondary)" }}>
              Estimates expected points and luck percentile from normalized OE, DE,
              QPct, forfeits, and optional Strength of Schedule.
            </p>
          </div>
          <button
            type="submit"
            disabled={loading}
            className="px-4 min-h-10 rounded-lg text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50 inline-flex items-center gap-1.5 cursor-pointer"
          >
            <Sparkles className="w-4 h-4" aria-hidden="true" />
            {loading ? "Analyzing..." : "Run Luck Analysis"}
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
          <div className="space-y-2.5">
            <div>
              <label htmlFor="luck-season" className="block text-xs font-medium mb-1">
                Season
              </label>
              <select
                id="luck-season"
                value={season}
                onChange={(e) => setSeason(Number(e.target.value))}
                className="ll-input w-full"
              >
                {seasonOptions.map((s) => (
                  <option key={s} value={s}>
                    LL {s}
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-1.5 pt-1">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={rundleFlag}
                  onChange={(e) => setRundleFlag(e.target.checked)}
                />
                Display Entire Rundle
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={useSos}
                  onChange={(e) => setUseSos(e.target.checked)}
                />
                Include Strength of Schedule (norm_SOS)
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={forceRefresh}
                  onChange={(e) => setForceRefresh(e.target.checked)}
                />
                Force Refresh League-Wide CSV
              </label>
            </div>
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between gap-2">
              <label htmlFor="luck-users" className="text-xs font-medium">
                Usernames (space or comma separated)
              </label>
              <div className="flex gap-1.5 text-xs">
                <button
                  type="button"
                  onClick={() => void handleLoadFavorites()}
                  className="ll-muted px-2 py-0.5 rounded cursor-pointer"
                >
                  Load Favs
                </button>
                <button
                  type="button"
                  onClick={() => void handleSaveFavorites()}
                  className="ll-muted px-2 py-0.5 rounded cursor-pointer"
                >
                  Save Favs
                </button>
                <button
                  type="button"
                  onClick={() => setUsernamesText("")}
                  className="ll-muted px-2 py-0.5 rounded cursor-pointer"
                >
                  Clear
                </button>
              </div>
            </div>
            <input
              id="luck-users"
              type="text"
              value={usernamesText}
              onChange={(e) => setUsernamesText(e.target.value)}
              placeholder="Leave blank to pick opponents or show top 250..."
              className="ll-input w-full"
            />
            {opponents.length > 0 && (
              <div>
                <label htmlFor="luck-opp-select" className="block text-xs font-medium mb-1">
                  Or select from Opponents (Ctrl/Cmd + click)
                </label>
                <select
                  id="luck-opp-select"
                  multiple
                  size={4}
                  value={selectedOpps}
                  onChange={(e) =>
                    setSelectedOpps(
                      Array.from(e.target.selectedOptions, (opt) => opt.value)
                    )
                  }
                  className="ll-input w-full text-xs"
                >
                  {opponents.map((o) => (
                    <option key={o} value={o}>
                      {o}
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>

          <div>
            <label htmlFor="luck-fields" className="block text-xs font-medium mb-1">
              Optional Extra Columns (Ctrl/Cmd + click)
            </label>
            <select
              id="luck-fields"
              multiple
              size={5}
              value={selectedFields}
              onChange={(e) =>
                setSelectedFields(
                  Array.from(e.target.selectedOptions, (opt) => opt.value)
                )
              }
              className="ll-input w-full text-xs"
            >
              {luckFields.map((f) => (
                <option key={f} value={f}>
                  {f}
                </option>
              ))}
            </select>

            <div className="mt-2 space-y-1.5">
              <span className="block text-xs font-medium">
                Custom Ratio Columns (A / B)
              </span>
              <div className="flex items-center gap-1.5">
                <select
                  aria-label="Ratio numerator column"
                  value={divideNum}
                  onChange={(e) => setDivideNum(e.target.value)}
                  className="ll-input text-xs flex-1"
                >
                  {["TMP", "TCA", "PTS", "W", "TPA", "CAA", "UfPA", "UfPE", ...luckFields].map(
                    (f) => (
                      <option key={`n-${f}`} value={f}>
                        {f}
                      </option>
                    )
                  )}
                </select>
                <span className="text-xs font-mono">/</span>
                <select
                  aria-label="Ratio denominator column"
                  value={divideDen}
                  onChange={(e) => setDivideDen(e.target.value)}
                  className="ll-input text-xs flex-1"
                >
                  {["TCA", "TMP", "Matches", "Played", "CAA", "W", ...luckFields].map(
                    (f) => (
                      <option key={`d-${f}`} value={f}>
                        {f}
                      </option>
                    )
                  )}
                </select>
                <button
                  type="button"
                  onClick={() => {
                    const exists = dividePairs.some(
                      ([a, b]) => a === divideNum && b === divideDen
                    );
                    if (!exists) {
                      setDividePairs([...dividePairs, [divideNum, divideDen]]);
                    }
                  }}
                  className="ll-muted px-2.5 py-1 rounded text-xs font-medium cursor-pointer"
                >
                  Add
                </button>
              </div>
              {dividePairs.length > 0 && (
                <div className="flex flex-wrap gap-1">
                  {dividePairs.map(([a, b]) => (
                    <button
                      key={`${a}/${b}`}
                      type="button"
                      onClick={() =>
                        setDividePairs(
                          dividePairs.filter(([x, y]) => !(x === a && y === b))
                        )
                      }
                      className="ll-muted px-2 py-0.5 rounded-full text-xs cursor-pointer"
                      title="Click to remove ratio"
                    >
                      {a}/{b} &times;
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>

        {error && (
          <p role="alert" className="text-sm text-red-600 dark:text-red-400">
            {error}
          </p>
        )}
      </form>

      {result && (
        <div className="space-y-3">
          {result.missing_usernames.length > 0 && (
            <div className="ll-card p-3 border-amber-500/50 bg-amber-500/10 flex items-center gap-2 text-sm">
              <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" aria-hidden="true" />
              <span>
                Not found in LL {result.season}:{" "}
                <strong>{result.missing_usernames.join(", ")}</strong>
              </span>
            </div>
          )}

          <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
            <div className="flex flex-wrap items-center gap-2">
              <span className="ll-muted px-2.5 py-1 rounded-full font-mono">
                LL {result.season} (MD {result.matchday})
              </span>
              <span className="ll-muted px-2.5 py-1 rounded-full font-mono">
                R&sup2; = {result.r_squared.toFixed(4)}
              </span>
              <span className="ll-muted px-2.5 py-1 rounded-full font-mono">
                {result.total_players.toLocaleString()} players modeled
              </span>
              <span className="ll-muted px-2.5 py-1 rounded-full font-mono">
                {result.formula}
              </span>
            </div>

            <button
              type="button"
              onClick={() => setHighlightFavs((v) => !v)}
              className="ll-muted px-3 py-1 rounded-lg font-medium inline-flex items-center gap-1 cursor-pointer"
            >
              <Star
                className="w-3.5 h-3.5 text-amber-500"
                fill={highlightFavs ? "currentColor" : "none"}
                aria-hidden="true"
              />
              {highlightFavs ? "Highlighting Favorites" : "Highlight Favorites"}
            </button>
          </div>

          <DataTable
            caption={`Luck Analysis Results for LL ${result.season}`}
            columns={columns}
            rows={result.rows}
            rowKey={(row, idx) => `${String(row.Player ?? idx)}-${idx}`}
            highlightRow={(row) => {
              if (!highlightFavs) return false;
              const p = String(row.Player ?? "").toLowerCase();
              return (
                result.matched_usernames.some((m) => m.toLowerCase() === p) ||
                favorites.some((f) => f.toLowerCase() === p)
              );
            }}
          />
        </div>
      )}
    </div>
  );
}

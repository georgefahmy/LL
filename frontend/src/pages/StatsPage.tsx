import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import { BarChart3, ExternalLink, RefreshCw, Star, Trash2, Users } from "lucide-react";

import { api } from "../api/client";
import { CategoryMetricsModal } from "../components/CategoryMetricsModal";
import { DataTable, type TableColumn } from "../components/DataTable";
import type { LocalStore } from "../storage/localStore";
import type { AuthMe, PlayerProfile } from "../types";

interface StatsPageProps {
  auth: AuthMe;
  statsDefinition: Record<string, string>;
  localStore: LocalStore;
  onRequireLogin: () => void;
}

export function StatsPage({
  auth,
  statsDefinition,
  localStore,
  onRequireLogin,
}: StatsPageProps) {
  const [myProfile, setMyProfile] = useState<PlayerProfile | null>(null);
  const [cachedNames, setCachedNames] = useState<string[]>([]);
  const [loadedPlayers, setLoadedPlayers] = useState<Record<string, PlayerProfile>>({});
  const [favorites, setFavorites] = useState<string[]>([]);
  const [searchInput, setSearchInput] = useState("");
  const [selectedDropdown, setSelectedDropdown] = useState("");
  const [seasonView, setSeasonView] = useState<"total" | "current_season">("total");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [metricsPlayer, setMetricsPlayer] = useState<PlayerProfile | null>(null);

  useEffect(() => {
    localStore.getFavorites().then(setFavorites);
  }, [localStore]);

  useEffect(() => {
    if (!auth.authenticated) return;
    setLoading(true);
    Promise.all([api.getMyProfile(), api.getCachedPlayerNames()])
      .then(([me, cached]) => {
        setMyProfile(me);
        setCachedNames(cached.usernames);
        setLoadedPlayers((prev) => ({ [me.formatted_username]: me, ...prev }));
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Failed loading profile.");
      })
      .finally(() => setLoading(false));
  }, [auth.authenticated]);

  const availableChoices = useMemo(() => {
    const oppNames = myProfile ? Object.keys(myProfile.opponents) : [];
    return Array.from(new Set([...oppNames, ...cachedNames])).sort((a, b) =>
      a.toLowerCase().localeCompare(b.toLowerCase())
    );
  }, [myProfile, cachedNames]);

  const fetchAndAddPlayer = useCallback(
    async (identifier: string, refresh = false) => {
      const clean = identifier.trim();
      if (!clean) return;
      setLoading(true);
      setError("");
      try {
        const oppId = myProfile?.opponents[clean];
        const profile = await api.getPlayerProfile(clean, oppId, refresh);
        setLoadedPlayers((prev) => ({
          ...prev,
          [profile.formatted_username]: profile,
        }));
        setCachedNames((prev) =>
          prev.includes(profile.formatted_username)
            ? prev
            : [...prev, profile.formatted_username].sort()
        );
      } catch (err) {
        setError(err instanceof Error ? err.message : `Player "${clean}" not found.`);
      } finally {
        setLoading(false);
      }
    },
    [myProfile]
  );

  const handleSearch = (e: FormEvent) => {
    e.preventDefault();
    void fetchAndAddPlayer(searchInput);
    setSearchInput("");
  };

  const handleLoadList = async (names: string[]) => {
    for (const name of names) {
      await fetchAndAddPlayer(name);
    }
  };

  const toggleFavorite = async (username: string) => {
    const exists = favorites.some((f) => f.toLowerCase() === username.toLowerCase());
    const next = exists
      ? favorites.filter((f) => f.toLowerCase() !== username.toLowerCase())
      : [...favorites, username];
    setFavorites(await localStore.setFavorites(next));
  };

  if (!auth.authenticated) {
    return (
      <div className="ll-card p-8 text-center space-y-3">
        <Users className="w-8 h-8 mx-auto opacity-60" aria-hidden="true" />
        <h1 className="text-lg font-semibold m-0">LearnedLeague Login Required</h1>
        <p className="text-sm m-0" style={{ color: "var(--text-secondary)" }}>
          Sign in with your LearnedLeague account to compare player statistics.
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

  const statKeys = Object.keys(statsDefinition);
  const tableRows = Object.values(loadedPlayers).map((p) => {
    const bucket = p.stats[seasonView] || {};
    const row: Record<string, unknown> = {
      Username: p.formatted_username,
      _profile: p,
    };
    for (const key of statKeys) {
      row[key] = bucket[key] ?? "--";
    }
    return row;
  });

  const numericStatKeys = new Set([
    "W",
    "L",
    "T",
    "PTS",
    "TMP",
    "TPA",
    "MPD",
    "TCA",
    "CAA",
    "PCAA",
    "UfPA",
    "DE",
    "FW",
    "FL",
    "3PT",
    "MCW",
    "QPct",
    "Rank",
  ]);

  const columns: TableColumn<Record<string, unknown>>[] = [
    {
      key: "Username",
      label: "Username",
      type: "text",
      render: (row) => {
        const p = row._profile as PlayerProfile;
        return (
          <a
            href={p.link}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 font-semibold text-blue-600 dark:text-blue-400 underline"
          >
            {p.formatted_username}
            <ExternalLink className="w-3 h-3" aria-hidden="true" />
          </a>
        );
      },
    },
    ...statKeys.map((k) => ({
      key: k,
      label: k,
      type: numericStatKeys.has(k) ? ("number" as const) : ("text" as const),
      title: statsDefinition[k],
    })),
    {
      key: "_actions",
      label: "Actions",
      sortable: false,
      render: (row) => {
        const p = row._profile as PlayerProfile;
        const isFav = favorites.some(
          (f) => f.toLowerCase() === p.formatted_username.toLowerCase()
        );
        return (
          <div className="inline-flex items-center gap-1.5">
            <button
              type="button"
              onClick={() => setMetricsPlayer(p)}
              title="Category Metrics"
              aria-label={`Category metrics for ${p.formatted_username}`}
              className="ll-muted p-1.5 rounded cursor-pointer"
            >
              <BarChart3 className="w-3.5 h-3.5" aria-hidden="true" />
            </button>
            <button
              type="button"
              onClick={() => void toggleFavorite(p.formatted_username)}
              title={isFav ? "Remove favorite" : "Add favorite"}
              aria-label={`Toggle favorite for ${p.formatted_username}`}
              className={`ll-muted p-1.5 rounded cursor-pointer ${
                isFav ? "text-amber-500" : ""
              }`}
            >
              <Star
                className="w-3.5 h-3.5"
                fill={isFav ? "currentColor" : "none"}
                aria-hidden="true"
              />
            </button>
            <button
              type="button"
              onClick={() => void fetchAndAddPlayer(p.formatted_username, true)}
              title="Refresh from LearnedLeague"
              aria-label={`Refresh ${p.formatted_username}`}
              className="ll-muted p-1.5 rounded cursor-pointer"
            >
              <RefreshCw className="w-3.5 h-3.5" aria-hidden="true" />
            </button>
            <button
              type="button"
              onClick={() =>
                setLoadedPlayers((prev) => {
                  const copy = { ...prev };
                  delete copy[p.formatted_username];
                  return copy;
                })
              }
              title="Remove row"
              aria-label={`Remove ${p.formatted_username}`}
              className="ll-muted p-1.5 rounded text-rose-600 dark:text-rose-400 cursor-pointer"
            >
              <Trash2 className="w-3.5 h-3.5" aria-hidden="true" />
            </button>
          </div>
        );
      },
    },
  ];

  return (
    <div className="space-y-4">
      <section className="ll-card p-4 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h1 className="text-lg font-semibold m-0">Player Tracker &amp; Statistics</h1>
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <button
              type="button"
              onClick={() =>
                setSeasonView((v) =>
                  v === "total" ? "current_season" : "total"
                )
              }
              className="px-3 py-1.5 rounded-lg font-medium text-white bg-blue-600 hover:bg-blue-700 cursor-pointer"
            >
              Showing: {seasonView === "total" ? "Career Total" : "Latest Season"}
            </button>
            <button
              type="button"
              disabled={loading || favorites.length === 0}
              onClick={() => void handleLoadList(favorites)}
              className="ll-muted px-3 py-1.5 rounded-lg font-medium disabled:opacity-40 cursor-pointer"
            >
              Load Favorites ({favorites.length})
            </button>
            <button
              type="button"
              disabled={loading || availableChoices.length === 0}
              onClick={() => void handleLoadList(availableChoices)}
              className="ll-muted px-3 py-1.5 rounded-lg font-medium disabled:opacity-40 cursor-pointer"
            >
              Load All ({availableChoices.length})
            </button>
            <button
              type="button"
              onClick={() => setLoadedPlayers({})}
              className="ll-muted px-3 py-1.5 rounded-lg font-medium cursor-pointer"
            >
              Clear All
            </button>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2.5 text-sm">
          <form onSubmit={handleSearch} className="flex items-center gap-2 flex-1 min-w-[240px]">
            <input
              type="text"
              aria-label="Search player username"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="Search LL username (e.g. FahmyG)..."
              className="ll-input flex-1"
            />
            <button
              type="submit"
              disabled={loading || !searchInput.trim()}
              className="px-3.5 min-h-9 rounded-lg font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-40 cursor-pointer"
            >
              Add Player
            </button>
          </form>

          <select
            aria-label="Select opponent or cached player"
            value={selectedDropdown}
            onChange={(e) => {
              const val = e.target.value;
              setSelectedDropdown(val);
              if (val) void fetchAndAddPlayer(val);
            }}
            className="ll-input min-w-[200px]"
          >
            <option value="">Quick Add Opponent / Cached...</option>
            {availableChoices.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </div>

        {error && (
          <p role="alert" className="text-sm text-red-600 dark:text-red-400">
            {error}
          </p>
        )}
      </section>

      <DataTable
        caption="LearnedLeague Player Statistics Comparison"
        columns={columns}
        rows={tableRows}
        rowKey={(row) => String(row.Username)}
      />

      {metricsPlayer && (
        <CategoryMetricsModal
          open={Boolean(metricsPlayer)}
          onClose={() => setMetricsPlayer(null)}
          username={metricsPlayer.formatted_username}
          metrics={metricsPlayer.category_metrics}
        />
      )}
    </div>
  );
}

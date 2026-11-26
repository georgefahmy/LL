import { useEffect, useMemo, useState, type FormEvent } from "react";
import { History, RefreshCw } from "lucide-react";

import { api } from "../api/client";
import { ImageLightbox } from "../components/ImageLightbox";
import { QuestionDrawer, type InspectedQuestion } from "../components/QuestionDrawer";
import type { AuthMe, PlayerProfile } from "../types";

interface HistoryPageProps {
  auth: AuthMe;
  categories: string[];
  onRequireLogin: () => void;
}

export function HistoryPage({
  auth,
  categories,
  onRequireLogin,
}: HistoryPageProps) {
  const [username, setUsername] = useState(auth.formatted_username || "");
  const [refresh, setRefresh] = useState(false);
  const [profile, setProfile] = useState<PlayerProfile | null>(null);
  const [search, setSearch] = useState("");
  const [catFilter, setCatFilter] = useState("ALL");
  const [selected, setSelected] = useState<Record<string, boolean>>({});
  const [inspected, setInspected] = useState<InspectedQuestion[]>([]);
  const [lightboxUrl, setLightboxUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!username && auth.formatted_username) {
      setUsername(auth.formatted_username);
    }
  }, [username, auth.formatted_username]);

  const handleFetch = async (e: FormEvent) => {
    e.preventDefault();
    const clean = username.trim();
    if (!clean) return;
    setLoading(true);
    setError("");
    setSelected({});
    try {
      const lowerClean = clean.toLowerCase();
      const matchesMe =
        lowerClean === (auth.username || "").toLowerCase() ||
        lowerClean === (auth.formatted_username || "").toLowerCase();
      const matchedProfileId =
        matchesMe && auth.profile_id ? auth.profile_id : undefined;
      const res = await api.getPlayerProfile(clean, matchedProfileId, refresh);
      setProfile(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed loading player history.");
    } finally {
      setLoading(false);
    }
  };

  const filtered = useMemo(() => {
    if (!profile) return [];
    const needle = search.trim().toLowerCase();
    return Object.entries(profile.question_history)
      .filter(([, v]) => {
        const catOk =
          catFilter === "ALL" ||
          v.question_category.toUpperCase() === catFilter.toUpperCase();
        const txtOk = !needle || v.question.toLowerCase().includes(needle);
        return catOk && txtOk;
      })
      .sort((a, b) => b[0].localeCompare(a[0]));
  }, [profile, search, catFilter]);

  const correctCount = useMemo(
    () => filtered.filter(([, v]) => v.correct).length,
    [filtered]
  );

  const inspectQcodes = async (qcodes: string[]) => {
    if (!profile || qcodes.length === 0) return;
    const items: InspectedQuestion[] = await Promise.all(
      qcodes.slice(0, 18).map(async (qc) => {
        const h = profile.question_history[qc];
        try {
          const qData = await api.getQuestion(qc);
          return {
            qcode: qc,
            questionData: qData,
            correct: h?.correct,
            llUrl: h?.url,
          };
        } catch {
          return {
            qcode: qc,
            fallbackText: h?.question,
            correct: h?.correct,
            llUrl: h?.url,
          };
        }
      })
    );
    setInspected(items);
  };

  if (!auth.authenticated) {
    return (
      <div className="ll-card p-8 text-center space-y-3">
        <History className="w-8 h-8 mx-auto opacity-60" aria-hidden="true" />
        <h1 className="text-lg font-semibold m-0">LearnedLeague Login Required</h1>
        <p className="text-sm m-0" style={{ color: "var(--text-secondary)" }}>
          Sign in with your LearnedLeague account to search any player&apos;s
          question history.
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

  return (
    <div className="space-y-4">
      <form onSubmit={handleFetch} className="ll-card p-4 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h1 className="text-lg font-semibold m-0">Player Question History</h1>
          {profile && (
            <span className="text-sm font-mono font-semibold">
              {profile.formatted_username}: {correctCount}/{filtered.length} Correct
            </span>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-2.5 text-sm">
          <input
            type="text"
            aria-label="Username to retrieve question history"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="Username (e.g. FahmyG)..."
            className="ll-input min-w-[200px]"
          />
          <label className="inline-flex items-center gap-1.5 text-xs cursor-pointer">
            <input
              type="checkbox"
              checked={refresh}
              onChange={(e) => setRefresh(e.target.checked)}
            />
            Refresh from LL
          </label>
          <button
            type="submit"
            disabled={loading || !username.trim()}
            className="px-4 min-h-9 rounded-lg font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-40 inline-flex items-center gap-1.5 cursor-pointer"
          >
            <RefreshCw className="w-3.5 h-3.5" aria-hidden="true" />
            {loading ? "Loading..." : "Retrieve Q-History"}
          </button>
        </div>

        {error && (
          <p role="alert" className="text-sm text-red-600 dark:text-red-400">
            {error}
          </p>
        )}
      </form>

      {profile && (
        <section className="ll-card p-4 space-y-3">
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <input
              type="search"
              aria-label="Filter question history by text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Filter questions by text..."
              className="ll-input flex-1 min-w-[200px]"
            />
            <select
              aria-label="Filter question history by category"
              value={catFilter}
              onChange={(e) => setCatFilter(e.target.value)}
              className="ll-input"
            >
              <option value="ALL">ALL Categories</option>
              {categories.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
            <button
              type="button"
              disabled={Object.values(selected).filter(Boolean).length === 0}
              onClick={() =>
                void inspectQcodes(
                  Object.keys(selected).filter((k) => selected[k])
                )
              }
              className="ll-muted px-3 py-1.5 rounded-lg text-xs font-medium disabled:opacity-40 cursor-pointer"
            >
              Open Selected
            </button>
          </div>

          <div
            className="max-h-[55vh] overflow-y-auto border rounded-lg divide-y text-sm"
            style={{ borderColor: "var(--border-subtle)" }}
          >
            {filtered.slice(0, 400).map(([qcode, item]) => (
              <div
                key={qcode}
                className="flex items-center justify-between gap-3 px-3 py-2 hover:bg-slate-500/5"
                style={{ borderColor: "var(--border-subtle)" }}
              >
                <label className="flex items-center gap-2.5 min-w-0 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={Boolean(selected[qcode])}
                    onChange={(e) =>
                      setSelected({ ...selected, [qcode]: e.target.checked })
                    }
                  />
                  <span className="font-mono text-xs font-semibold shrink-0">
                    {qcode}
                  </span>
                  <span className="text-xs px-2 py-0.5 rounded ll-muted shrink-0">
                    {item.question_category}
                  </span>
                  <span className="text-xs truncate" style={{ color: "var(--text-secondary)" }}>
                    {item.question}
                  </span>
                </label>

                <div className="flex items-center gap-2 shrink-0">
                  <span
                    className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                      item.correct
                        ? "bg-emerald-600/15 text-emerald-700 dark:text-emerald-300"
                        : "bg-rose-600/15 text-rose-700 dark:text-rose-300"
                    }`}
                  >
                    {item.correct ? "Correct" : "Incorrect"}
                  </span>
                  <button
                    type="button"
                    onClick={() => void inspectQcodes([qcode])}
                    className="text-xs text-blue-600 dark:text-blue-400 underline cursor-pointer"
                  >
                    View
                  </button>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      <QuestionDrawer
        items={inspected}
        onClose={() => setInspected([])}
        onOpenImage={setLightboxUrl}
      />
      <ImageLightbox imageUrl={lightboxUrl} onClose={() => setLightboxUrl(null)} />
    </div>
  );
}

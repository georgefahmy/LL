import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import { BookOpen, ExternalLink, RefreshCw, RotateCcw, Shuffle } from "lucide-react";

import { api } from "../api/client";
import { LookupPopover } from "../components/LookupPopover";
import type { MiniLeagueCatalogItem, MiniLeagueDetail } from "../types";

interface MiniAttemptState {
  input: string;
  submitted: boolean;
  correct: boolean;
  override: boolean;
  revealed: boolean;
}

export function MiniLeaguesPage() {
  const [catalog, setCatalog] = useState<MiniLeagueCatalogItem[]>([]);
  const [search, setSearch] = useState("");
  const [selectedSlug, setSelectedSlug] = useState("");
  const [detail, setDetail] = useState<MiniLeagueDetail | null>(null);
  const [loadingList, setLoadingList] = useState(true);
  const [loadingMini, setLoadingMini] = useState(false);
  const [error, setError] = useState("");
  const [attempts, setAttempts] = useState<Record<number, MiniAttemptState>>({});
  const [lookupState, setLookupState] = useState<{
    loading: boolean;
    result: { term: string; source: string; summary: string } | null;
  }>({ loading: false, result: null });

  const initAttempts = useCallback((mini: MiniLeagueDetail) => {
    const next: Record<number, MiniAttemptState> = {};
    for (const day of mini.match_days) {
      for (const q of day.questions) {
        next[q.index] = {
          input: "",
          submitted: false,
          correct: false,
          override: false,
          revealed: false,
        };
      }
    }
    setAttempts(next);
  }, []);

  const loadMini = useCallback(
    async (slug: string) => {
      if (!slug) return;
      setLoadingMini(true);
      setError("");
      try {
        const res = await api.getMiniLeagueDetail(slug);
        setDetail(res);
        setSelectedSlug(slug);
        initAttempts(res);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load Mini League.");
      } finally {
        setLoadingMini(false);
      }
    },
    [initAttempts]
  );

  const loadCatalog = useCallback(
    async (refresh = false) => {
      setLoadingList(true);
      setError("");
      try {
        const res = await api.getMiniLeagues("", refresh);
        setCatalog(res.items);
        if (res.items.length > 0 && !selectedSlug) {
          const pick = res.items[Math.floor(Math.random() * res.items.length)];
          await loadMini(pick.slug);
        }
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Failed to load Mini Leagues catalog."
        );
      } finally {
        setLoadingList(false);
      }
    },
    [loadMini, selectedSlug]
  );

  useEffect(() => {
    void loadCatalog(false);
  }, []);

  const filteredCatalog = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return catalog;
    return catalog.filter((it) => it.title.toLowerCase().includes(q));
  }, [catalog, search]);

  const score = useMemo(
    () => Object.values(attempts).filter((a) => a.submitted && a.correct).length,
    [attempts]
  );

  const handleSubmit = async (e: FormEvent, idx: number, answerText: string) => {
    e.preventDefault();
    const st = attempts[idx];
    if (!st || !st.input.trim() || st.submitted) return;
    const res = await api.gradeAnswer(st.input, answerText);
    setAttempts({
      ...attempts,
      [idx]: { ...st, submitted: true, correct: res.correct, revealed: true },
    });
  };

  const handleRandom = () => {
    const pool = filteredCatalog.length > 0 ? filteredCatalog : catalog;
    if (pool.length === 0) return;
    const pick = pool[Math.floor(Math.random() * pool.length)];
    void loadMini(pick.slug);
  };

  const handleLookupSelection = async () => {
    const sel = window.getSelection()?.toString().trim() ?? "";
    if (!sel) return;
    setLookupState({ loading: true, result: null });
    try {
      const res = await api.lookupTerm(sel);
      setLookupState({ loading: false, result: res });
    } catch {
      setLookupState({
        loading: false,
        result: { term: sel, source: "error", summary: "Lookup failed." },
      });
    }
  };

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <section className="ll-card p-4 space-y-3">
          <div className="flex items-center justify-between">
            <h1 className="text-base font-semibold m-0">Mini League Selection</h1>
            <div className="flex items-center gap-1.5">
              <button
                type="button"
                onClick={handleRandom}
                disabled={loadingList}
                className="ll-muted px-2.5 py-1 rounded-lg text-xs font-medium inline-flex items-center gap-1 cursor-pointer"
              >
                <Shuffle className="w-3.5 h-3.5" aria-hidden="true" />
                Random
              </button>
              <button
                type="button"
                onClick={() => void loadCatalog(true)}
                disabled={loadingList}
                title="Refresh catalog"
                className="ll-muted p-1.5 rounded-lg cursor-pointer"
              >
                <RefreshCw className="w-3.5 h-3.5" aria-hidden="true" />
              </button>
            </div>
          </div>

          <div className="space-y-2 text-sm">
            <input
              type="search"
              aria-label="Filter Mini League titles"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={`Filter ${catalog.length} Mini Leagues...`}
              className="ll-input w-full"
            />
            <select
              aria-label="Choose Mini League"
              value={selectedSlug}
              onChange={(e) => void loadMini(e.target.value)}
              className="ll-input w-full"
            >
              {filteredCatalog.map((item) => (
                <option key={item.slug} value={item.slug}>
                  {item.title} ({item.date})
                </option>
              ))}
            </select>
          </div>
        </section>

        <section className="ll-card p-4 space-y-2">
          <div className="flex items-start justify-between gap-2">
            <h2 className="text-base font-semibold m-0">{detail?.title || "Loading..."}</h2>
            {detail?.url && (
              <a
                href={detail.url}
                target="_blank"
                rel="noreferrer"
                className="text-xs text-blue-600 dark:text-blue-400 underline shrink-0 inline-flex items-center gap-1"
              >
                LL <ExternalLink className="w-3 h-3" aria-hidden="true" />
              </a>
            )}
          </div>
          {detail && (
            <dl className="grid grid-cols-2 gap-y-1 text-sm m-0">
              <dt style={{ color: "var(--text-secondary)" }}>Date</dt>
              <dd className="text-right font-medium m-0">{detail.date || "--"}</dd>
              <dt style={{ color: "var(--text-secondary)" }}>Overall % Correct</dt>
              <dd className="text-right font-mono font-semibold m-0">
                {detail.overall_correct}%
              </dd>
              <dt style={{ color: "var(--text-secondary)" }}>Players</dt>
              <dd className="text-right font-mono m-0">{detail.num_players || "--"}</dd>
              <dt style={{ color: "var(--text-secondary)" }}>Questions</dt>
              <dd className="text-right font-mono m-0">{detail.total_questions}</dd>
            </dl>
          )}
        </section>

        <section className="ll-card p-4 flex flex-col justify-between gap-3">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-semibold m-0">Progress</h2>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={handleLookupSelection}
                className="ll-muted px-2.5 py-1 rounded-lg text-xs font-medium inline-flex items-center gap-1 cursor-pointer"
              >
                <BookOpen className="w-3.5 h-3.5" aria-hidden="true" />
                Lookup
              </button>
              <button
                type="button"
                onClick={() => detail && initAttempts(detail)}
                className="ll-muted px-2.5 py-1 rounded-lg text-xs font-medium inline-flex items-center gap-1 cursor-pointer"
              >
                <RotateCcw className="w-3.5 h-3.5" aria-hidden="true" />
                Reset Quiz
              </button>
            </div>
          </div>
          <div className="ll-muted p-3 rounded-lg">
            <div className="text-xs" style={{ color: "var(--text-secondary)" }}>
              Total Score
            </div>
            <div className="text-2xl font-bold font-mono">
              {score} / {detail?.total_questions ?? 0}
            </div>
          </div>
        </section>
      </div>

      {error && (
        <p role="alert" className="text-sm text-red-600 dark:text-red-400">
          {error}
        </p>
      )}

      {loadingMini ? (
        <div className="ll-card p-6 text-sm" style={{ color: "var(--text-secondary)" }}>
          Fetching Mini League match days (cached locally after first load)...
        </div>
      ) : (
        detail && (
          <div className="space-y-6">
            {detail.match_days.map((md) => (
              <section key={md.day} className="space-y-3">
                <h3 className="text-sm font-bold uppercase tracking-wider px-1" style={{ color: "var(--text-secondary)" }}>
                  Match Day {md.day} &mdash; {md.label}
                </h3>
                {md.questions.map((q) => {
                  const st = attempts[q.index];
                  if (!st) return null;
                  return (
                    <article key={q.index} className="ll-card p-4 space-y-2.5">
                      <div className="flex items-start justify-between gap-3">
                        <div className="space-y-1">
                          <span className="text-xs font-mono font-bold px-2 py-0.5 rounded ll-muted">
                            #{q.index} ({q.label})
                          </span>
                          <p className="text-base leading-relaxed select-text">
                            {q.question}
                          </p>
                        </div>
                        {(st.submitted || st.revealed) && (
                          <span className="text-xs font-mono px-2.5 py-1 rounded-full ll-muted shrink-0">
                            {q.percent}% Correct
                          </span>
                        )}
                      </div>

                      <div className="flex flex-wrap items-center gap-3 text-sm">
                        <button
                          type="button"
                          onClick={() =>
                            setAttempts({
                              ...attempts,
                              [q.index]: { ...st, revealed: !st.revealed },
                            })
                          }
                          disabled={st.submitted}
                          className="ll-muted px-3 py-1.5 rounded-lg text-xs font-medium disabled:opacity-50 cursor-pointer"
                        >
                          {st.revealed ? "Hide Answer" : "Show Answer"}
                        </button>
                        <span className="font-semibold">
                          {st.revealed ? q.answer : "••••••••"}
                        </span>
                      </div>

                      <form
                        onSubmit={(e) => void handleSubmit(e, q.index, q.answer)}
                        className="flex flex-wrap items-center gap-2"
                      >
                        <input
                          type="text"
                          value={st.input}
                          disabled={st.submitted}
                          onChange={(e) =>
                            setAttempts({
                              ...attempts,
                              [q.index]: { ...st, input: e.target.value },
                            })
                          }
                          placeholder="Type your answer..."
                          className={`ll-input flex-1 min-w-[200px] ${
                            st.submitted
                              ? st.correct
                                ? "!bg-emerald-500/20 !border-emerald-500"
                                : "!bg-rose-500/20 !border-rose-500"
                              : ""
                          }`}
                        />
                        <button
                          type="submit"
                          disabled={st.submitted || !st.input.trim()}
                          className="px-3.5 min-h-9 rounded-lg text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-40 cursor-pointer"
                        >
                          Submit
                        </button>
                        {st.submitted && (
                          <label className="inline-flex items-center gap-1.5 text-xs cursor-pointer">
                            <input
                              type="checkbox"
                              checked={st.override}
                              onChange={() =>
                                setAttempts({
                                  ...attempts,
                                  [q.index]: {
                                    ...st,
                                    correct: !st.correct,
                                    override: !st.override,
                                  },
                                })
                              }
                            />
                            Ans Override
                          </label>
                        )}
                      </form>
                    </article>
                  );
                })}
              </section>
            ))}
          </div>
        )
      )}

      <LookupPopover
        result={lookupState.result}
        loading={lookupState.loading}
        onClose={() => setLookupState({ loading: false, result: null })}
      />
    </div>
  );
}

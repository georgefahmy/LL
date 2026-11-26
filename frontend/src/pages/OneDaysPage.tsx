import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import { BookOpen, ChevronDown, ChevronUp, ExternalLink, RefreshCw, RotateCcw, Shuffle } from "lucide-react";

import { api } from "../api/client";
import { LookupPopover } from "../components/LookupPopover";
import { ModalDialog } from "../components/ModalDialog";
import type { LocalStore } from "../storage/localStore";
import type { OneDayCatalogItem, OneDayDetail } from "../types";

interface OneDaysPageProps {
  modkosUrl: string;
  localStore: LocalStore;
}

interface QuestionAttemptState {
  input: string;
  money: boolean;
  submitted: boolean;
  forfeited: boolean;
  correct: boolean;
  override: boolean;
  revealed: boolean;
}

export function OneDaysPage({ modkosUrl, localStore }: OneDaysPageProps) {
  const [catalog, setCatalog] = useState<OneDayCatalogItem[]>([]);
  const [search, setSearch] = useState("");
  const [selectedSlug, setSelectedSlug] = useState<string>("");
  const [detail, setDetail] = useState<OneDayDetail | null>(null);
  const [loadingList, setLoadingList] = useState(true);
  const [loadingQuiz, setLoadingQuiz] = useState(false);
  const [error, setError] = useState("");
  const [showBlurb, setShowBlurb] = useState(false);

  const [attempts, setAttempts] = useState<Record<string, QuestionAttemptState>>({});
  const [confirmForfeitQ, setConfirmForfeitQ] = useState<string | null>(null);
  const [lookupState, setLookupState] = useState<{
    loading: boolean;
    result: { term: string; source: string; summary: string } | null;
  }>({ loading: false, result: null });

  const initAttempts = useCallback((od: OneDayDetail) => {
    const next: Record<string, QuestionAttemptState> = {};
    for (const q of od.questions) {
      next[q.question_num] = {
        input: "",
        money: false,
        submitted: false,
        forfeited: false,
        correct: false,
        override: false,
        revealed: false,
      };
    }
    setAttempts(next);
  }, []);

  const loadQuiz = useCallback(
    async (slug: string) => {
      if (!slug) return;
      setLoadingQuiz(true);
      setError("");
      try {
        const od = await api.getOneDayDetail(slug);
        setDetail(od);
        setSelectedSlug(slug);
        initAttempts(od);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load OneDay.");
      } finally {
        setLoadingQuiz(false);
      }
    },
    [initAttempts]
  );

  const loadCatalog = useCallback(
    async (refresh = false) => {
      setLoadingList(true);
      setError("");
      try {
        const res = await api.getOneDays("", refresh);
        setCatalog(res.items);
        if (res.items.length > 0 && !selectedSlug) {
          const pick = res.items[Math.floor(Math.random() * res.items.length)];
          await loadQuiz(pick.slug);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to fetch OneDays catalog.");
      } finally {
        setLoadingList(false);
      }
    },
    [loadQuiz, selectedSlug]
  );

  useEffect(() => {
    void loadCatalog(false);
  }, []);

  const filteredCatalog = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return catalog;
    return catalog.filter((item) => item.title.toLowerCase().includes(q));
  }, [catalog, search]);

  const { score, moneyLeft, completedCount, totalCount } = useMemo(() => {
    if (!detail) return { score: 0, moneyLeft: 5, completedCount: 0, totalCount: 0 };
    let pts = 0;
    let moneyUsed = 0;
    let done = 0;
    for (const q of detail.questions) {
      const st = attempts[q.question_num];
      if (!st) continue;
      if (st.submitted || st.forfeited) done += 1;
      if (st.submitted && st.money) moneyUsed += 1;
      if (st.submitted && st.correct) {
        pts += 15 + (st.money ? Math.max(0, 100 - q.percent) : 0);
      }
    }
    return {
      score: pts,
      moneyLeft: Math.max(0, 5 - moneyUsed),
      completedCount: done,
      totalCount: detail.questions.length,
    };
  }, [detail, attempts]);

  const finalPercentile = useMemo(() => {
    if (!detail || completedCount < totalCount || totalCount === 0) return null;
    const entries = Object.entries(detail.percentiles || {});
    if (entries.length === 0) return "N/A";
    let bestPct = entries[0][0];
    let bestDiff = Math.abs(entries[0][1] - score);
    for (const [pct, val] of entries) {
      const diff = Math.abs(val - score);
      if (diff < bestDiff) {
        bestDiff = diff;
        bestPct = pct;
      }
    }
    return `${bestPct}%`;
  }, [detail, completedCount, totalCount, score]);

  const persistIfComplete = useCallback(
    async (nextAttempts: Record<string, QuestionAttemptState>, od: OneDayDetail) => {
      const done = od.questions.filter(
        (q) => nextAttempts[q.question_num]?.submitted || nextAttempts[q.question_num]?.forfeited
      ).length;
      if (done !== od.questions.length || od.questions.length === 0) return;

      let totalScore = 0;
      for (const q of od.questions) {
        const st = nextAttempts[q.question_num];
        if (st?.submitted && st.correct) {
          totalScore += 15 + (st.money ? Math.max(0, 100 - q.percent) : 0);
        }
      }
      const entries = Object.entries(od.percentiles || {});
      let pctLabel = "NONE";
      if (entries.length > 0) {
        pctLabel = entries.reduce((best, cur) =>
          Math.abs(cur[1] - totalScore) < Math.abs(best[1] - totalScore) ? cur : best
        )[0];
      }
      await localStore.saveOneDayAttempt({
        slug: od.slug,
        title: od.title,
        score: totalScore,
        percentile: pctLabel,
        payload: { attempts: nextAttempts },
      });
    },
    [localStore]
  );

  const handleSubmitQuestion = async (e: FormEvent, qNum: string, answerText: string) => {
    e.preventDefault();
    if (!detail) return;
    const st = attempts[qNum];
    if (!st || !st.input.trim() || st.submitted || st.forfeited) return;

    const res = await api.gradeAnswer(st.input, answerText);
    const next = {
      ...attempts,
      [qNum]: {
        ...st,
        submitted: true,
        correct: res.correct,
        revealed: true,
      },
    };
    setAttempts(next);
    await persistIfComplete(next, detail);
  };

  const handleRevealClick = (qNum: string) => {
    const st = attempts[qNum];
    if (!st) return;
    if (!st.submitted && !st.forfeited && !st.input.trim()) {
      setConfirmForfeitQ(qNum);
      return;
    }
    setAttempts({
      ...attempts,
      [qNum]: { ...st, revealed: !st.revealed },
    });
  };

  const handleConfirmForfeit = async () => {
    if (!confirmForfeitQ || !detail) return;
    const qNum = confirmForfeitQ;
    const st = attempts[qNum];
    setConfirmForfeitQ(null);
    if (!st) return;
    const next = {
      ...attempts,
      [qNum]: {
        ...st,
        forfeited: true,
        money: false,
        correct: false,
        revealed: true,
      },
    };
    setAttempts(next);
    await persistIfComplete(next, detail);
  };

  const handleOverride = async (qNum: string) => {
    if (!detail) return;
    const st = attempts[qNum];
    if (!st || !st.submitted) return;
    const next = {
      ...attempts,
      [qNum]: {
        ...st,
        correct: !st.correct,
        override: !st.override,
      },
    };
    setAttempts(next);
    await persistIfComplete(next, detail);
  };

  const handleRandom = () => {
    const pool = filteredCatalog.length > 0 ? filteredCatalog : catalog;
    if (pool.length === 0) return;
    const pick = pool[Math.floor(Math.random() * pool.length)];
    void loadQuiz(pick.slug);
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
        {/* Selection */}
        <section className="ll-card p-4 space-y-3">
          <div className="flex items-center justify-between">
            <h1 className="text-base font-semibold m-0">OneDay Selection</h1>
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
            <div>
              <label htmlFor="od-search" className="block text-xs font-medium mb-1">
                Filter Titles
              </label>
              <input
                id="od-search"
                type="search"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder={`Search ${catalog.length} OneDays...`}
                className="ll-input w-full"
              />
            </div>
            <div>
              <label htmlFor="od-select" className="block text-xs font-medium mb-1">
                Choose OneDay ({filteredCatalog.length})
              </label>
              <select
                id="od-select"
                value={selectedSlug}
                onChange={(e) => void loadQuiz(e.target.value)}
                className="ll-input w-full"
              >
                {filteredCatalog.map((item) => (
                  <option key={item.slug} value={item.slug}>
                    {item.title} ({item.date})
                  </option>
                ))}
              </select>
            </div>
          </div>
        </section>

        {/* Info */}
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
            <>
              <dl className="grid grid-cols-2 gap-y-1 text-sm m-0">
                <dt style={{ color: "var(--text-secondary)" }}>Date</dt>
                <dd className="text-right font-medium m-0">{detail.date || "--"}</dd>
                <dt style={{ color: "var(--text-secondary)" }}>
                  <a
                    href={modkosUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="underline text-blue-600 dark:text-blue-400"
                  >
                    ModKos Difficulty
                  </a>
                </dt>
                <dd className="text-right font-medium m-0">{detail.difficulty_rating}</dd>
                <dt style={{ color: "var(--text-secondary)" }}>Avg % Correct</dt>
                <dd className="text-right font-mono font-semibold m-0">
                  {detail.overall_average}%
                </dd>
                <dt style={{ color: "var(--text-secondary)" }}>Players</dt>
                <dd className="text-right font-mono m-0">{detail.number_of_players}</dd>
              </dl>
              {detail.blurb && (
                <button
                  type="button"
                  onClick={() => setShowBlurb((v) => !v)}
                  className="text-xs text-blue-600 dark:text-blue-400 inline-flex items-center gap-1 cursor-pointer"
                >
                  {showBlurb ? (
                    <>
                      <ChevronUp className="w-3.5 h-3.5" aria-hidden="true" /> Hide Description
                    </>
                  ) : (
                    <>
                      <ChevronDown className="w-3.5 h-3.5" aria-hidden="true" /> Show Description
                    </>
                  )}
                </button>
              )}
            </>
          )}
        </section>

        {/* Score & Percentiles */}
        <section className="ll-card p-4 space-y-2.5">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-semibold m-0">Scoreboard</h2>
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
                Reset
              </button>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-2 text-sm">
            <div className="ll-muted p-2.5 rounded-lg">
              <div className="text-xs" style={{ color: "var(--text-secondary)" }}>
                Current Score
              </div>
              <div className="text-xl font-bold font-mono">{score} pts</div>
            </div>
            <div className="ll-muted p-2.5 rounded-lg">
              <div className="text-xs" style={{ color: "var(--text-secondary)" }}>
                Money Qs Left
              </div>
              <div className="text-xl font-bold font-mono">{moneyLeft} / 5</div>
            </div>
          </div>
          {detail && (
            <div className="flex justify-between text-xs" style={{ color: "var(--text-secondary)" }}>
              <span>90th: {detail.p90 ?? "--"}</span>
              <span>50th: {detail.p50 ?? "--"}</span>
              <span>10th: {detail.p10 ?? "--"}</span>
            </div>
          )}
          {finalPercentile !== null && (
            <div className="p-2.5 rounded-lg bg-emerald-600/15 text-emerald-700 dark:text-emerald-300 text-sm font-semibold">
              Completed ({completedCount}/{totalCount}): {score} pts &mdash; Est. Percentile:{" "}
              {finalPercentile}
            </div>
          )}
        </section>
      </div>

      {showBlurb && detail?.blurb && (
        <div className="ll-card p-4 text-sm whitespace-pre-line">{detail.blurb}</div>
      )}

      {error && (
        <p role="alert" className="text-sm text-red-600 dark:text-red-400">
          {error}
        </p>
      )}

      {loadingQuiz ? (
        <div className="ll-card p-6 text-sm" style={{ color: "var(--text-secondary)" }}>
          Loading OneDay questions...
        </div>
      ) : (
        detail && (
          <div className="space-y-3">
            {detail.questions.map((q) => {
              const st = attempts[q.question_num];
              if (!st) return null;
              const locked = st.submitted || st.forfeited;
              const moneyDisabled = locked || (moneyLeft <= 0 && !st.money);

              return (
                <article key={q.question_num} className="ll-card p-4 space-y-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="space-y-1">
                      <span className="text-xs font-mono font-bold px-2 py-0.5 rounded ll-muted">
                        Q{q.question_num}
                      </span>
                      <p className="text-base leading-relaxed select-text">{q.question}</p>
                    </div>
                    {locked && (
                      <span className="text-xs font-mono px-2.5 py-1 rounded-full ll-muted shrink-0">
                        {q.percent}% Correct
                      </span>
                    )}
                  </div>

                  <div className="flex flex-wrap items-center gap-3 text-sm">
                    <button
                      type="button"
                      onClick={() => handleRevealClick(q.question_num)}
                      className="ll-muted px-3 py-1.5 rounded-lg text-xs font-medium cursor-pointer"
                    >
                      {st.revealed ? "Hide Answer" : "Show Answer"}
                    </button>
                    <span className="font-semibold">
                      {st.revealed ? q.answer : "••••••••"}
                    </span>
                    <label
                      className={`ml-auto inline-flex items-center gap-1.5 text-sm ${
                        moneyDisabled ? "opacity-50" : "cursor-pointer"
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={st.money}
                        disabled={moneyDisabled}
                        onChange={(e) =>
                          setAttempts({
                            ...attempts,
                            [q.question_num]: { ...st, money: e.target.checked },
                          })
                        }
                      />
                      Money Question
                    </label>
                  </div>

                  <form
                    onSubmit={(e) => void handleSubmitQuestion(e, q.question_num, q.answer)}
                    className="flex flex-wrap items-center gap-2"
                  >
                    <input
                      type="text"
                      value={st.input}
                      disabled={locked}
                      onChange={(e) =>
                        setAttempts({
                          ...attempts,
                          [q.question_num]: { ...st, input: e.target.value },
                        })
                      }
                      placeholder={
                        st.forfeited ? "Forfeited" : "Type your answer..."
                      }
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
                      disabled={locked || !st.input.trim()}
                      className="px-3.5 min-h-9 rounded-lg text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-40 cursor-pointer"
                    >
                      Submit
                    </button>
                    {st.submitted && (
                      <label className="inline-flex items-center gap-1.5 text-xs cursor-pointer">
                        <input
                          type="checkbox"
                          checked={st.override}
                          onChange={() => void handleOverride(q.question_num)}
                        />
                        Ans Override
                      </label>
                    )}
                  </form>
                </article>
              );
            })}
          </div>
        )
      )}

      <ModalDialog
        open={Boolean(confirmForfeitQ)}
        onClose={() => setConfirmForfeitQ(null)}
        title="Forfeit Question?"
      >
        <div className="space-y-4">
          <p className="text-sm">
            You haven&apos;t submitted an answer for Question {confirmForfeitQ}.
            Revealing the answer now will forfeit your guess on this question.
          </p>
          <div className="flex justify-end gap-2">
            <button
              type="button"
              autoFocus
              onClick={() => setConfirmForfeitQ(null)}
              className="ll-muted px-4 min-h-9 rounded-lg text-sm font-medium cursor-pointer"
            >
              Keep Trying
            </button>
            <button
              type="button"
              onClick={() => void handleConfirmForfeit()}
              className="px-4 min-h-9 rounded-lg text-sm font-medium text-white bg-rose-600 hover:bg-rose-700 cursor-pointer"
            >
              Reveal &amp; Forfeit
            </button>
          </div>
        </div>
      </ModalDialog>

      <LookupPopover
        result={lookupState.result}
        loading={lookupState.loading}
        onClose={() => setLookupState({ loading: false, result: null })}
      />
    </div>
  );
}

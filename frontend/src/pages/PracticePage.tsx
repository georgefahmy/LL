import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import {
  BookOpen,
  ChevronLeft,
  ChevronRight,
  ExternalLink,
  Eye,
  EyeOff,
  Image as ImageIcon,
  Shuffle,
} from "lucide-react";

import { api } from "../api/client";
import { ImageLightbox } from "../components/ImageLightbox";
import { LookupPopover } from "../components/LookupPopover";
import type { LocalStore } from "../storage/localStore";
import type { PracticeAnswerRecord, QuestionItem } from "../types";

interface PracticePageProps {
  categories: string[];
  localStore: LocalStore;
}

export function PracticePage({ categories, localStore }: PracticePageProps) {
  const [search, setSearch] = useState("");
  const [season, setSeason] = useState("ALL");
  const [category, setCategory] = useState("ALL");
  const [minPct, setMinPct] = useState(0);
  const [maxPct, setMaxPct] = useState(100);

  const [items, setItems] = useState<QuestionItem[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [localIdx, setLocalIdx] = useState(0);
  const [availSeasons, setAvailSeasons] = useState<number[]>([]);
  const [availCategories, setAvailCategories] = useState<string[]>(categories);
  const [loading, setLoading] = useState(true);

  const [answerVisible, setAnswerVisible] = useState(false);
  const [submission, setSubmission] = useState("");
  const [gradeState, setGradeState] = useState<{
    submitted: string;
    correct: boolean;
    override: boolean;
    recordId: number | string | null;
  } | null>(null);
  const [history, setHistory] = useState<PracticeAnswerRecord[]>([]);
  const [lightboxUrl, setLightboxUrl] = useState<string | null>(null);
  const [lookupState, setLookupState] = useState<{
    loading: boolean;
    result: { term: string; source: string; summary: string } | null;
  }>({ loading: false, result: null });

  const questionRef = useRef<HTMLParagraphElement>(null);
  const PAGE_SIZE = 50;

  const currentQuestion = items[localIdx] ?? null;

  const loadPage = useCallback(
    async (
      nextOffset: number,
      targetIdx = 0,
      filters?: {
        search: string;
        season: string;
        category: string;
        minPct: number;
        maxPct: number;
      }
    ) => {
      const f = filters ?? { search, season, category, minPct, maxPct };
      setLoading(true);
      try {
        const res = await api.getQuestions({
          min_pct: f.minPct,
          max_pct: Math.max(f.minPct, f.maxPct),
          category: f.category,
          season: f.season,
          search: f.search,
          limit: PAGE_SIZE,
          offset: nextOffset,
        });
        setItems(res.items);
        setTotal(res.total);
        setOffset(nextOffset);
        setLocalIdx(Math.min(targetIdx, Math.max(0, res.items.length - 1)));
        if (res.seasons.length > 0) setAvailSeasons(res.seasons);
        if (res.categories.length > 0) setAvailCategories(res.categories);
        setAnswerVisible(false);
        setSubmission("");
        setGradeState(null);
      } finally {
        setLoading(false);
      }
    },
    [search, season, category, minPct, maxPct]
  );

  // Initial load picks a random question like the desktop app
  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const res = await api.getQuestions({ limit: PAGE_SIZE, offset: 0 });
        setItems(res.items);
        setTotal(res.total);
        setAvailSeasons(res.seasons);
        if (res.categories.length > 0) setAvailCategories(res.categories);
        if (res.items.length > 0) {
          setLocalIdx(Math.floor(Math.random() * res.items.length));
        }
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  useEffect(() => {
    if (!currentQuestion) {
      setHistory([]);
      return;
    }
    localStore.listPracticeAnswers(currentQuestion.qcode).then(setHistory);
  }, [currentQuestion, localStore]);

  const handleRandom = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.getQuestions({
        min_pct: minPct,
        max_pct: Math.max(minPct, maxPct),
        category,
        season,
        search,
        random: true,
      });
      if (res.items.length > 0) {
        setItems(res.items);
        setTotal(res.total);
        setOffset(0);
        setLocalIdx(0);
        setAnswerVisible(false);
        setSubmission("");
        setGradeState(null);
      }
    } finally {
      setLoading(false);
    }
  }, [minPct, maxPct, category, season, search]);

  const handleNext = useCallback(() => {
    if (localIdx + 1 < items.length) {
      setLocalIdx((i) => i + 1);
      setAnswerVisible(false);
      setSubmission("");
      setGradeState(null);
    } else if (offset + PAGE_SIZE < total) {
      void loadPage(offset + PAGE_SIZE, 0);
    }
  }, [localIdx, items.length, offset, total, loadPage]);

  const handlePrev = useCallback(() => {
    if (localIdx > 0) {
      setLocalIdx((i) => i - 1);
      setAnswerVisible(false);
      setSubmission("");
      setGradeState(null);
    } else if (offset >= PAGE_SIZE) {
      void loadPage(offset - PAGE_SIZE, PAGE_SIZE - 1);
    }
  }, [localIdx, offset, loadPage]);

  // Keyboard shortcuts (Cmd/Ctrl+S/R/N/P or plain keys when not typing in an input)
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      const inInput =
        target &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.tagName === "SELECT");
      const hasMod = e.metaKey || e.ctrlKey;
      if (!hasMod && inInput) return;
      if (inInput && hasMod) return;

      const key = e.key.toLowerCase();
      if (key === "s" && (hasMod || !inInput)) {
        e.preventDefault();
        setAnswerVisible((v) => !v);
      } else if (key === "r" && (hasMod || !inInput)) {
        e.preventDefault();
        void handleRandom();
      } else if (key === "n" && (hasMod || !inInput)) {
        e.preventDefault();
        handleNext();
      } else if (key === "p" && (hasMod || !inInput)) {
        e.preventDefault();
        handlePrev();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [handleRandom, handleNext, handlePrev]);

  const handleFilterSubmit = (e: FormEvent) => {
    e.preventDefault();
    void loadPage(0, 0);
  };

  const handleGradeSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!currentQuestion || !submission.trim() || gradeState) return;
    const res = await api.gradeAnswer(submission, currentQuestion.answer);
    setAnswerVisible(true);
    const id = await localStore.recordPracticeAnswer({
      qcode: currentQuestion.qcode,
      submitted_answer: submission.trim(),
      correct: res.correct,
      override: false,
    });
    setGradeState({
      submitted: submission.trim(),
      correct: res.correct,
      override: false,
      recordId: id,
    });
    setHistory(await localStore.listPracticeAnswers(currentQuestion.qcode));
  };

  const handleToggleOverride = async () => {
    if (!gradeState || !currentQuestion) return;
    const nextCorrect = !gradeState.correct;
    const nextOverride = !gradeState.override;
    if (gradeState.recordId !== null) {
      await localStore.overridePracticeAnswer(
        gradeState.recordId,
        nextCorrect,
        nextOverride
      );
      setHistory(await localStore.listPracticeAnswers(currentQuestion.qcode));
    }
    setGradeState({ ...gradeState, correct: nextCorrect, override: nextOverride });
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
        result: {
          term: sel,
          source: "error",
          summary: "Lookup failed. Please try another selection.",
        },
      });
    }
  };

  const globalIndex = total > 0 ? offset + localIdx + 1 : 0;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Filters */}
        <form onSubmit={handleFilterSubmit} className="ll-card p-4 space-y-3">
          <div className="flex items-center justify-between">
            <h1 className="text-base font-semibold m-0">Filters</h1>
            <button
              type="submit"
              className="px-3 py-1.5 rounded-lg text-xs font-medium text-white bg-blue-600 hover:bg-blue-700 cursor-pointer"
            >
              Apply Filter
            </button>
          </div>
          <div className="grid grid-cols-2 gap-2.5 text-sm">
            <div className="col-span-2">
              <label htmlFor="p-search" className="block text-xs font-medium mb-1">
                Search Question Text
              </label>
              <input
                id="p-search"
                type="search"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Keyword..."
                className="ll-input w-full"
              />
            </div>
            <div>
              <label htmlFor="p-season" className="block text-xs font-medium mb-1">
                Season
              </label>
              <select
                id="p-season"
                value={season}
                onChange={(e) => {
                  const val = e.target.value;
                  setSeason(val);
                  void loadPage(0, 0, {
                    search,
                    season: val,
                    category,
                    minPct,
                    maxPct,
                  });
                }}
                className="ll-input w-full"
              >
                <option value="ALL">ALL</option>
                {availSeasons.map((s) => (
                  <option key={s} value={String(s)}>
                    LL {s}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor="p-cat" className="block text-xs font-medium mb-1">
                Category
              </label>
              <select
                id="p-cat"
                value={category}
                onChange={(e) => {
                  const val = e.target.value;
                  setCategory(val);
                  void loadPage(0, 0, {
                    search,
                    season,
                    category: val,
                    minPct,
                    maxPct,
                  });
                }}
                className="ll-input w-full"
              >
                <option value="ALL">ALL</option>
                {availCategories.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor="p-min" className="block text-xs font-medium mb-1">
                Min % Correct
              </label>
              <input
                id="p-min"
                type="number"
                min={0}
                max={100}
                value={minPct}
                onChange={(e) => setMinPct(Number(e.target.value))}
                className="ll-input w-full"
              />
            </div>
            <div>
              <label htmlFor="p-max" className="block text-xs font-medium mb-1">
                Max % Correct
              </label>
              <input
                id="p-max"
                type="number"
                min={0}
                max={100}
                value={maxPct}
                onChange={(e) => setMaxPct(Number(e.target.value))}
                className="ll-input w-full"
              />
            </div>
          </div>
        </form>

        {/* Rundle Metrics */}
        <section className="ll-card p-4 space-y-2.5">
          <h2 className="text-base font-semibold m-0">Rundle % Correct</h2>
          <div className="grid grid-cols-3 gap-2 text-sm">
            {(["A", "B", "C", "D", "E", "R"] as const).map((r) => (
              <div key={r} className="ll-muted px-3 py-2 rounded-lg flex justify-between">
                <span className="font-medium">Rundle {r}</span>
                <span className="font-mono font-semibold">
                  {currentQuestion?.rundles[r] ? `${currentQuestion.rundles[r]}%` : "--"}
                </span>
              </div>
            ))}
          </div>
        </section>

        {/* Question Metrics */}
        <section className="ll-card p-4 space-y-2">
          <h2 className="text-base font-semibold m-0">Question Metrics</h2>
          {currentQuestion ? (
            <dl className="grid grid-cols-2 gap-y-1.5 text-sm m-0">
              <dt style={{ color: "var(--text-secondary)" }}>Date</dt>
              <dd className="text-right font-medium m-0">{currentQuestion.date || "--"}</dd>
              <dt style={{ color: "var(--text-secondary)" }}>Season</dt>
              <dd className="text-right font-medium m-0">LL {currentQuestion.season}</dd>
              <dt style={{ color: "var(--text-secondary)" }}>Question</dt>
              <dd className="text-right font-medium m-0">
                <a
                  href={currentQuestion.url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 text-blue-600 dark:text-blue-400 underline"
                >
                  {currentQuestion.question_num}
                  <ExternalLink className="w-3 h-3" aria-hidden="true" />
                </a>
              </dd>
              <dt style={{ color: "var(--text-secondary)" }}>Category</dt>
              <dd className="text-right font-medium m-0">{currentQuestion.category}</dd>
              <dt style={{ color: "var(--text-secondary)" }}>% Correct</dt>
              <dd className="text-right font-mono font-semibold m-0">
                {currentQuestion.percent}%
              </dd>
              <dt style={{ color: "var(--text-secondary)" }}>Defense Value</dt>
              <dd className="text-right font-mono font-semibold m-0">
                {currentQuestion.defense || "--"}
              </dd>
            </dl>
          ) : (
            <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
              No question selected.
            </p>
          )}
        </section>
      </div>

      {/* Question Card */}
      <section className="ll-card p-5 space-y-4">
        {loading ? (
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            Loading questions...
          </p>
        ) : !currentQuestion ? (
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            No questions match the current filters. Try widening the % or clearing search.
          </p>
        ) : (
          <>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="text-xs font-mono px-2.5 py-1 rounded-full ll-muted">
                {currentQuestion.qcode} &bull; {globalIndex} of {total.toLocaleString()}
              </span>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={handleLookupSelection}
                  title="Select text inside the question first, then click to look up"
                  className="ll-muted px-3 py-1.5 rounded-lg text-xs font-medium inline-flex items-center gap-1.5 cursor-pointer"
                >
                  <BookOpen className="w-3.5 h-3.5" aria-hidden="true" />
                  Lookup Selection
                </button>
                {currentQuestion.clickable_link && (
                  <button
                    type="button"
                    onClick={() => setLightboxUrl(currentQuestion.clickable_link)}
                    className="px-3 py-1.5 rounded-lg text-xs font-medium text-white bg-indigo-600 hover:bg-indigo-700 inline-flex items-center gap-1.5 cursor-pointer"
                  >
                    <ImageIcon className="w-3.5 h-3.5" aria-hidden="true" />
                    View Media
                  </button>
                )}
              </div>
            </div>

            <p
              ref={questionRef}
              className="text-lg md:text-xl leading-relaxed font-normal select-text"
            >
              {currentQuestion.question}
            </p>

            {/* Answer reveal & navigation */}
            <div className="flex flex-wrap items-center justify-between gap-3 pt-2 border-t" style={{ borderColor: "var(--border-subtle)" }}>
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={() => setAnswerVisible((v) => !v)}
                  className="ll-muted px-3.5 min-h-9 rounded-lg text-sm font-medium inline-flex items-center gap-1.5 cursor-pointer"
                >
                  {answerVisible ? (
                    <>
                      <EyeOff className="w-4 h-4" aria-hidden="true" />
                      Hide Answer
                    </>
                  ) : (
                    <>
                      <Eye className="w-4 h-4" aria-hidden="true" />
                      Show Answer
                    </>
                  )}
                </button>
                <span className="font-semibold text-base">
                  {answerVisible ? currentQuestion.answer : "••••••••"}
                </span>
              </div>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => void handleRandom()}
                  className="ll-muted px-3 min-h-9 rounded-lg text-sm font-medium inline-flex items-center gap-1.5 cursor-pointer"
                  title="Random question (R)"
                >
                  <Shuffle className="w-4 h-4" aria-hidden="true" />
                  Random
                </button>
                <button
                  type="button"
                  onClick={handlePrev}
                  disabled={globalIndex <= 1}
                  className="ll-muted px-3 min-h-9 rounded-lg text-sm font-medium inline-flex items-center gap-1 disabled:opacity-40 cursor-pointer"
                  title="Previous (P)"
                >
                  <ChevronLeft className="w-4 h-4" aria-hidden="true" />
                  Prev
                </button>
                <button
                  type="button"
                  onClick={handleNext}
                  disabled={globalIndex >= total}
                  className="ll-muted px-3 min-h-9 rounded-lg text-sm font-medium inline-flex items-center gap-1 disabled:opacity-40 cursor-pointer"
                  title="Next (N)"
                >
                  Next
                  <ChevronRight className="w-4 h-4" aria-hidden="true" />
                </button>
              </div>
            </div>

            {/* Submit Answer */}
            <form onSubmit={handleGradeSubmit} className="flex flex-wrap items-center gap-2.5">
              <label htmlFor="practice-answer-input" className="visually-hidden">
                Your answer
              </label>
              <input
                id="practice-answer-input"
                type="text"
                value={submission}
                disabled={Boolean(gradeState)}
                onChange={(e) => setSubmission(e.target.value)}
                placeholder="Type your answer and press Enter..."
                className={`ll-input flex-1 min-w-[220px] ${
                  gradeState
                    ? gradeState.correct
                      ? "!bg-emerald-500/20 !border-emerald-500"
                      : "!bg-rose-500/20 !border-rose-500"
                    : ""
                }`}
              />
              <button
                type="submit"
                disabled={Boolean(gradeState) || !submission.trim()}
                className="px-4 min-h-10 rounded-lg text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-40 cursor-pointer"
              >
                Submit Answer
              </button>
              {gradeState && (
                <label className="inline-flex items-center gap-1.5 text-sm cursor-pointer">
                  <input
                    type="checkbox"
                    checked={gradeState.override}
                    onChange={handleToggleOverride}
                  />
                  Ans Override ({gradeState.correct ? "Marked Correct" : "Marked Incorrect"})
                </label>
              )}
            </form>

            {history.length > 0 && (
              <div className="text-xs pt-2 border-t" style={{ borderColor: "var(--border-subtle)", color: "var(--text-secondary)" }}>
                <strong>Your past attempts on {currentQuestion.qcode}:</strong>{" "}
                {history
                  .slice(0, 5)
                  .map(
                    (h) =>
                      `"${h.submitted_answer}" (${h.correct ? "Correct" : "Incorrect"})`
                  )
                  .join(" • ")}
              </div>
            )}
          </>
        )}
      </section>

      <ImageLightbox imageUrl={lightboxUrl} onClose={() => setLightboxUrl(null)} />
      <LookupPopover
        result={lookupState.result}
        loading={lookupState.loading}
        onClose={() => setLookupState({ loading: false, result: null })}
      />
    </div>
  );
}

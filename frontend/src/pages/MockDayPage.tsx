import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import { Eye, EyeOff, Image as ImageIcon, RefreshCw } from "lucide-react";

import { api } from "../api/client";
import { ImageLightbox } from "../components/ImageLightbox";
import type { LocalStore } from "../storage/localStore";
import type { MockDayPayload } from "../types";

interface MockDayPageProps {
  localStore: LocalStore;
}

export function MockDayPage({ localStore }: MockDayPageProps) {
  const [randomSeed, setRandomSeed] = useState(false);
  const [threshold, setThreshold] = useState(0);
  const [mockDay, setMockDay] = useState<MockDayPayload | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [grades, setGrades] = useState<
    Record<string, { correct: boolean; override: boolean }>
  >({});
  const [submitted, setSubmitted] = useState(false);
  const [showAnswers, setShowAnswers] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [lightboxUrl, setLightboxUrl] = useState<string | null>(null);

  const generate = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const seedVal = randomSeed ? Math.floor(Math.random() * 1000) : null;
      const payload = await api.generateMockDay(seedVal, threshold);
      setMockDay(payload);
      setAnswers({});
      setGrades({});
      setSubmitted(false);
      setShowAnswers(false);
      await localStore.saveMockDay({
        uuid: payload.uuid,
        code: payload.code,
        seed: payload.seed,
        threshold: payload.threshold,
        payload: { ...payload },
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed generating Mock Match Day.");
    } finally {
      setLoading(false);
    }
  }, [randomSeed, threshold, localStore]);

  useEffect(() => {
    void generate();
  }, []);

  const handleSubmitAll = async (e: FormEvent) => {
    e.preventDefault();
    if (!mockDay || submitted) return;
    const nextGrades: Record<string, { correct: boolean; override: boolean }> = {};
    await Promise.all(
      mockDay.questions.map(async (q) => {
        const sub = (answers[q.qcode] || "").trim();
        if (!sub) {
          nextGrades[q.qcode] = { correct: false, override: false };
          return;
        }
        const res = await api.gradeAnswer(sub, q.answer);
        nextGrades[q.qcode] = { correct: res.correct, override: false };
      })
    );
    setGrades(nextGrades);
    setSubmitted(true);
    setShowAnswers(true);
  };

  const totalMatchPoints = useMemo(() => {
    if (!mockDay || !submitted) return 0;
    return mockDay.questions.reduce((acc, q) => {
      return acc + (grades[q.qcode]?.correct ? q.assigned_point : 0);
    }, 0);
  }, [mockDay, submitted, grades]);

  const totalCorrectCount = useMemo(() => {
    if (!mockDay || !submitted) return 0;
    return mockDay.questions.filter((q) => grades[q.qcode]?.correct).length;
  }, [mockDay, submitted, grades]);

  return (
    <div className="space-y-4">
      <section className="ll-card p-4 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-lg font-semibold m-0">Mock Match Day (6 Questions)</h1>
          <p className="text-xs m-0" style={{ color: "var(--text-secondary)" }}>
            Deterministic daily set (or toggle Random Seed) with difficulty-assigned
            points (3, 2, 2, 1, 1, 0).
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3 text-sm">
          <label className="inline-flex items-center gap-1.5 cursor-pointer">
            <input
              type="checkbox"
              checked={randomSeed}
              onChange={(e) => setRandomSeed(e.target.checked)}
            />
            Random Seed
          </label>
          <div className="flex items-center gap-1.5">
            <label htmlFor="mock-thresh" className="text-xs font-medium">
              Min % Correct:
            </label>
            <select
              id="mock-thresh"
              value={threshold}
              onChange={(e) => setThreshold(Number(e.target.value))}
              className="ll-input"
            >
              {Array.from({ length: 20 }, (_, i) => i * 5).map((val) => (
                <option key={val} value={val}>
                  {val}%
                </option>
              ))}
            </select>
          </div>
          <button
            type="button"
            onClick={() => void generate()}
            disabled={loading}
            className="px-3.5 min-h-9 rounded-lg font-medium text-white bg-blue-600 hover:bg-blue-700 inline-flex items-center gap-1.5 cursor-pointer"
          >
            <RefreshCw className="w-4 h-4" aria-hidden="true" />
            New Questions
          </button>
        </div>
      </section>

      {error && (
        <p role="alert" className="text-sm text-red-600 dark:text-red-400">
          {error}
        </p>
      )}

      {submitted && (
        <div className="ll-card p-4 bg-emerald-600/10 border-emerald-500/40 flex flex-wrap items-center justify-between gap-2">
          <span className="font-semibold">
            Final Match Score: {totalMatchPoints}({totalCorrectCount})
          </span>
          <span className="text-xs font-mono" style={{ color: "var(--text-secondary)" }}>
            Set ID: {mockDay?.code}
          </span>
        </div>
      )}

      {loading ? (
        <div className="ll-card p-6 text-sm" style={{ color: "var(--text-secondary)" }}>
          Generating Mock Match Day...
        </div>
      ) : (
        mockDay && (
          <form onSubmit={(e) => void handleSubmitAll(e)} className="space-y-3">
            {mockDay.questions.map((q) => {
              const g = grades[q.qcode];
              return (
                <article key={q.qcode} className="ll-card p-4 space-y-2.5">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-mono font-bold px-2 py-0.5 rounded ll-muted">
                        Q{q.index}
                      </span>
                      <span className="text-xs font-medium ll-muted px-2 py-0.5 rounded">
                        {q.category}
                      </span>
                      {q.clickable_link && (
                        <button
                          type="button"
                          onClick={() => setLightboxUrl(q.clickable_link)}
                          className="text-xs text-blue-600 dark:text-blue-400 underline inline-flex items-center gap-1 cursor-pointer"
                        >
                          <ImageIcon className="w-3.5 h-3.5" aria-hidden="true" />
                          View Media
                        </button>
                      )}
                    </div>
                    {(submitted || showAnswers) && (
                      <div className="flex items-center gap-2 text-xs font-mono">
                        <span className="px-2 py-0.5 rounded bg-blue-600/15 text-blue-700 dark:text-blue-300 font-semibold">
                          Pts: {q.assigned_point}
                        </span>
                        <span className="px-2 py-0.5 rounded ll-muted">
                          {q.percent}% Correct
                        </span>
                      </div>
                    )}
                  </div>

                  <p className="text-base leading-relaxed">{q.question}</p>

                  <div className="flex flex-wrap items-center gap-2">
                    <input
                      type="text"
                      value={answers[q.qcode] ?? ""}
                      disabled={submitted}
                      onChange={(e) =>
                        setAnswers({ ...answers, [q.qcode]: e.target.value })
                      }
                      placeholder={`Answer for Q${q.index}...`}
                      className={`ll-input flex-1 min-w-[220px] ${
                        submitted && g
                          ? g.correct
                            ? "!bg-emerald-500/20 !border-emerald-500"
                            : "!bg-rose-500/20 !border-rose-500"
                          : ""
                      }`}
                    />
                    {submitted && g && (
                      <label className="inline-flex items-center gap-1.5 text-xs cursor-pointer">
                        <input
                          type="checkbox"
                          checked={g.override}
                          onChange={() =>
                            setGrades({
                              ...grades,
                              [q.qcode]: {
                                correct: !g.correct,
                                override: !g.override,
                              },
                            })
                          }
                        />
                        Ans Override
                      </label>
                    )}
                  </div>

                  {showAnswers && (
                    <div className="text-sm pt-1">
                      <span style={{ color: "var(--text-secondary)" }}>
                        Correct Answer:{" "}
                      </span>
                      <span className="font-semibold text-emerald-700 dark:text-emerald-300">
                        {q.answer}
                      </span>
                    </div>
                  )}
                </article>
              );
            })}

            <div className="flex flex-wrap items-center gap-3 pt-2">
              <button
                type="submit"
                disabled={submitted}
                className="px-5 min-h-10 rounded-lg font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-40 cursor-pointer"
              >
                Submit Match Day
              </button>
              <button
                type="button"
                onClick={() => setShowAnswers((v) => !v)}
                className="ll-muted px-4 min-h-10 rounded-lg font-medium inline-flex items-center gap-1.5 cursor-pointer"
              >
                {showAnswers ? (
                  <>
                    <EyeOff className="w-4 h-4" aria-hidden="true" /> Hide Answers
                  </>
                ) : (
                  <>
                    <Eye className="w-4 h-4" aria-hidden="true" /> Show Answers
                  </>
                )}
              </button>
            </div>
          </form>
        )
      )}

      <ImageLightbox imageUrl={lightboxUrl} onClose={() => setLightboxUrl(null)} />
    </div>
  );
}

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ClipboardEvent as ReactClipboardEvent,
  type DragEvent,
  type FormEvent,
} from "react";
import {
  Activity,
  BarChart3,
  CalendarClock,
  Camera,
  ChevronDown,
  ClipboardPaste,
  RefreshCw,
  Shield,
  Trash2,
  Upload,
  Users,
  ZoomIn,
} from "lucide-react";

import { api } from "../api/client";
import { CategoryMetricsModal } from "../components/CategoryMetricsModal";
import { ImageLightbox } from "../components/ImageLightbox";
import { ModalDialog } from "../components/ModalDialog";
import { QuestionDrawer, type InspectedQuestion } from "../components/QuestionDrawer";
import { RadarChart } from "../components/RadarChart";
import type {
  AuthMe,
  CategoryMetric,
  DefenseRecommendation,
  PlayerProfile,
  RadarPoint,
  TodaysQuestionsResponse,
} from "../types";

interface DefensePageProps {
  auth: AuthMe;
  categories: string[];
  latestSeason: number;
  currentDay: number;
  onRequireLogin: () => void;
}

const DIFFICULTY_LEVELS: { value: number; label: string; title: string }[] = [
  { value: 1, label: "1", title: "Gimme (~90%)" },
  { value: 2, label: "2", title: "Easy (~75%)" },
  { value: 3, label: "3", title: "Med (~50%)" },
  { value: 4, label: "4", title: "Hard (~25%)" },
  { value: 5, label: "5", title: "Stump (~10%)" },
];

const MY_STATS_STORAGE_KEY = "ll-defense-my-stats-v1";

type DefenseMode = "screenshot" | "live";
type ShotTab = "opponent" | "me" | "questions";

interface OcrTabStatus {
  loading: boolean;
  matched: number | null;
  missing: string[];
  rawText: string;
  error: string;
}

const EMPTY_OCR_STATUS: OcrTabStatus = {
  loading: false,
  matched: null,
  missing: [],
  rawText: "",
  error: "",
};

function loadStoredMyStats(): Record<string, CategoryMetric> {
  try {
    const raw = localStorage.getItem(MY_STATS_STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as unknown;
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      return parsed as Record<string, CategoryMetric>;
    }
  } catch {
    // Ignore storage parse errors
  }
  return {};
}

async function fileToApiDataUrl(file: File): Promise<string> {
  const rawDataUrl = await new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result === "string") resolve(reader.result);
      else reject(new Error("Could not read screenshot file."));
    };
    reader.onerror = () => reject(new Error("Could not read screenshot file."));
    reader.readAsDataURL(file);
  });

  // Keep payload comfortably under the 5 MB API body limit
  if (rawDataUrl.length <= 3_500_000) {
    return rawDataUrl;
  }

  return await new Promise<string>((resolve) => {
    const img = new Image();
    img.onload = () => {
      const maxDim = 2200;
      const scale = Math.min(1, maxDim / Math.max(img.width, img.height));
      const canvas = document.createElement("canvas");
      canvas.width = Math.max(1, Math.round(img.width * scale));
      canvas.height = Math.max(1, Math.round(img.height * scale));
      const ctx = canvas.getContext("2d");
      if (!ctx) {
        resolve(rawDataUrl);
        return;
      }
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      resolve(canvas.toDataURL("image/jpeg", 0.9));
    };
    img.onerror = () => resolve(rawDataUrl);
    img.src = rawDataUrl;
  });
}

export function DefensePage({
  auth,
  categories,
  latestSeason,
  currentDay,
  onRequireLogin,
}: DefensePageProps) {
  const [defenseMode, setDefenseMode] = useState<DefenseMode>(() =>
    auth.authenticated ? "live" : "screenshot"
  );

  // Live LL mode state
  const [p1Input, setP1Input] = useState("");
  const [p1Profile, setP1Profile] = useState<PlayerProfile | null>(null);
  const [opponentInput, setOpponentInput] = useState("");
  const [oppProfile, setOppProfile] = useState<PlayerProfile | null>(null);
  const [oppMenuOpen, setOppMenuOpen] = useState(false);
  const oppComboRef = useRef<HTMLDivElement | null>(null);

  const [hunResult, setHunResult] = useState<{
    score: number;
    shared_questions: number;
    matching_outcomes: number;
  } | null>(null);

  const [radarData, setRadarData] = useState<{
    open: boolean;
    player1: string;
    player2: string;
    series: RadarPoint[];
  }>({ open: false, player1: "", player2: "", series: [] });

  const [showMetrics, setShowMetrics] = useState(false);

  const [todaysModal, setTodaysModal] = useState<{
    open: boolean;
    showAnswers: boolean;
    loading: boolean;
    data: TodaysQuestionsResponse | null;
  }>({ open: false, showAnswers: false, loading: false, data: null });

  // Shared 6-question Defense Strategy form state
  const [slotCats, setSlotCats] = useState<string[]>(Array(6).fill(""));
  const [slotDiffs, setSlotDiffs] = useState<(number | null)[]>(Array(6).fill(null));
  const [recs, setRecs] = useState<DefenseRecommendation[] | null>(null);
  const [defenseMeta, setDefenseMeta] = useState<{
    mode: "irt" | "category_only";
    expectedOpponentPoints: number;
  } | null>(null);

  // Screenshot / Offline mode state
  const [activeShotTab, setActiveShotTab] = useState<ShotTab>("opponent");
  const [manualOppMetrics, setManualOppMetrics] = useState<Record<string, CategoryMetric>>({});
  const [manualMyMetrics, setManualMyMetrics] = useState<Record<string, CategoryMetric>>(
    loadStoredMyStats
  );
  const [shotPreviews, setShotPreviews] = useState<Record<ShotTab, string | null>>({
    opponent: null,
    me: null,
    questions: null,
  });
  const [ocrStatus, setOcrStatus] = useState<Record<"opponent" | "me", OcrTabStatus>>({
    opponent: EMPTY_OCR_STATUS,
    me: EMPTY_OCR_STATUS,
  });
  const [showTextFallback, setShowTextFallback] = useState<Record<"opponent" | "me", boolean>>({
    opponent: false,
    me: false,
  });
  const [textFallbackInput, setTextFallbackInput] = useState<Record<"opponent" | "me", string>>({
    opponent: "",
    me: "",
  });
  const [showEditableTable, setShowEditableTable] = useState<Record<"opponent" | "me", boolean>>({
    opponent: true,
    me: true,
  });
  const [screenshotLightbox, setScreenshotLightbox] = useState<{
    url: string;
    title: string;
  } | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const [qSearch, setQSearch] = useState("");
  const [qCategory, setQCategory] = useState("ALL");
  const [selectedQcodes, setSelectedQcodes] = useState<Record<string, boolean>>({});
  const [inspected, setInspected] = useState<InspectedQuestion[]>([]);
  const [lightboxUrl, setLightboxUrl] = useState<string | null>(null);

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    try {
      localStorage.setItem(MY_STATS_STORAGE_KEY, JSON.stringify(manualMyMetrics));
    } catch {
      // Ignore storage quota errors
    }
  }, [manualMyMetrics]);

  useEffect(() => {
    if (!oppMenuOpen) return;
    const handleMouseDown = (e: MouseEvent) => {
      if (oppComboRef.current && !oppComboRef.current.contains(e.target as Node)) {
        setOppMenuOpen(false);
      }
    };
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setOppMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", handleMouseDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handleMouseDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [oppMenuOpen]);

  const loadPlayersInitial = useCallback(async () => {
    if (!auth.authenticated) return;
    setBusy(true);
    setError("");
    try {
      const me = await api.getMyProfile();
      setP1Profile(me);
      setP1Input(me.formatted_username);
      const oppNames = Object.keys(me.opponents);
      if (oppNames.length > 0) {
        const defaultOpp = oppNames[Math.min(oppNames.length - 1, currentDay)];
        setOpponentInput(defaultOpp);
        const opp = await api.getPlayerProfile(
          defaultOpp,
          me.opponents[defaultOpp]
        );
        setOppProfile(opp);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed loading player data.");
    } finally {
      setBusy(false);
    }
  }, [auth.authenticated, currentDay]);

  useEffect(() => {
    void loadPlayersInitial();
  }, [loadPlayersInitial]);

  const loadOpponent = useCallback(
    async (name: string, refresh = false): Promise<PlayerProfile | null> => {
      const clean = name.trim();
      if (!clean) return null;
      setBusy(true);
      setError("");
      try {
        const pid = p1Profile?.opponents[clean];
        const opp = await api.getPlayerProfile(clean, pid, refresh);
        setOppProfile(opp);
        return opp;
      } catch (err) {
        setError(err instanceof Error ? err.message : "Opponent not found.");
        return null;
      } finally {
        setBusy(false);
      }
    },
    [p1Profile]
  );

  const loadPlayer1 = useCallback(async (name: string, refresh = false) => {
    const clean = name.trim();
    if (!clean) return;
    setBusy(true);
    setError("");
    try {
      const p1 = await api.getPlayerProfile(clean, undefined, refresh);
      setP1Profile(p1);
      const oppNames = Object.keys(p1.opponents);
      if (oppNames.length > 0) {
        const defaultOpp = oppNames[Math.min(oppNames.length - 1, currentDay)];
        setOpponentInput(defaultOpp);
        const opp = await api.getPlayerProfile(
          defaultOpp,
          p1.opponents[defaultOpp]
        );
        setOppProfile(opp);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Player not found.");
    } finally {
      setBusy(false);
    }
  }, [currentDay]);

  const handleCalculateHun = async () => {
    if (!p1Input || !opponentInput) return;
    setBusy(true);
    setError("");
    try {
      const res = await api.getHun(
        p1Input,
        opponentInput,
        p1Profile?.opponents[opponentInput]
      );
      setHunResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed calculating HUN.");
    } finally {
      setBusy(false);
    }
  };

  const handleShowSimilarity = async () => {
    if (!p1Input || !opponentInput) return;
    setBusy(true);
    setError("");
    try {
      const res = await api.getSimilarity(
        p1Input,
        opponentInput,
        p1Profile?.opponents[opponentInput]
      );
      setRadarData({
        open: true,
        player1: res.player1,
        player2: res.player2,
        series: res.series,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed loading radar chart.");
    } finally {
      setBusy(false);
    }
  };

  const handleOpenTodaysQuestions = async (
    showAns = todaysModal.showAnswers,
    targetDay = currentDay + 1
  ) => {
    setTodaysModal((prev) => ({
      ...prev,
      open: true,
      loading: true,
      showAnswers: showAns,
      data: null,
    }));
    try {
      const data = await api.getTodaysQuestions(showAns, latestSeason, targetDay);
      setTodaysModal({ open: true, showAnswers: showAns, loading: false, data });
    } catch (err) {
      setTodaysModal((prev) => ({ ...prev, open: false, loading: false }));
      setError(
        err instanceof Error ? err.message : "Failed loading Match Day questions."
      );
    }
  };

  const processScreenshotForTab = useCallback(async (tab: ShotTab, file: File) => {
    setError("");
    try {
      const dataUrl = await fileToApiDataUrl(file);
      setShotPreviews((prev) => ({ ...prev, [tab]: dataUrl }));

      if (tab === "questions") {
        return;
      }

      setOcrStatus((prev) => ({
        ...prev,
        [tab]: { ...prev[tab], loading: true, error: "" },
      }));
      const parsed = await api.parseStatsScreenshot({ image_base64: dataUrl });
      if (tab === "opponent") {
        setManualOppMetrics(parsed.category_metrics);
      } else {
        setManualMyMetrics(parsed.category_metrics);
      }
      setOcrStatus((prev) => ({
        ...prev,
        [tab]: {
          loading: false,
          matched: parsed.matched_count,
          missing: parsed.missing_categories,
          rawText: parsed.raw_text,
          error:
            parsed.matched_count === 0
              ? "No category rows detected in screenshot. Try cropping tighter or use Paste Table Text below."
              : "",
        },
      }));
      setTextFallbackInput((prev) => ({ ...prev, [tab]: parsed.raw_text }));
      setShowEditableTable((prev) => ({ ...prev, [tab]: true }));
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed processing screenshot.";
      if (tab === "opponent" || tab === "me") {
        setOcrStatus((prev) => ({
          ...prev,
          [tab]: { ...prev[tab], loading: false, error: msg },
        }));
      } else {
        setError(msg);
      }
    }
  }, []);

  const handleParseTextFallback = async (tab: "opponent" | "me") => {
    const raw = textFallbackInput[tab].trim();
    if (!raw) {
      setOcrStatus((prev) => ({
        ...prev,
        [tab]: { ...prev[tab], error: "Paste category stats text first." },
      }));
      return;
    }
    setOcrStatus((prev) => ({
      ...prev,
      [tab]: { ...prev[tab], loading: true, error: "" },
    }));
    try {
      const parsed = await api.parseStatsScreenshot({ raw_text: raw });
      if (tab === "opponent") {
        setManualOppMetrics(parsed.category_metrics);
      } else {
        setManualMyMetrics(parsed.category_metrics);
      }
      setOcrStatus((prev) => ({
        ...prev,
        [tab]: {
          loading: false,
          matched: parsed.matched_count,
          missing: parsed.missing_categories,
          rawText: parsed.raw_text,
          error:
            parsed.matched_count === 0
              ? "Could not match any LearnedLeague categories in that text."
              : "",
        },
      }));
      setShowEditableTable((prev) => ({ ...prev, [tab]: true }));
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed parsing pasted stats text.";
      setOcrStatus((prev) => ({
        ...prev,
        [tab]: { ...prev[tab], loading: false, error: msg },
      }));
    }
  };

  useEffect(() => {
    if (defenseMode !== "screenshot") return;
    const onWindowPaste = (e: ClipboardEvent) => {
      const items = e.clipboardData?.items;
      if (!items) return;
      for (const item of items) {
        if (item.type.startsWith("image/")) {
          const file = item.getAsFile();
          if (file) {
            e.preventDefault();
            void processScreenshotForTab(activeShotTab, file);
            return;
          }
        }
      }
    };
    window.addEventListener("paste", onWindowPaste);
    return () => window.removeEventListener("paste", onWindowPaste);
  }, [defenseMode, activeShotTab, processScreenshotForTab]);

  const handleDropScreenshot = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    const file = e.dataTransfer.files?.[0];
    if (file && file.type.startsWith("image/")) {
      void processScreenshotForTab(activeShotTab, file);
    }
  };

  const handlePasteZone = (e: ReactClipboardEvent<HTMLDivElement>) => {
    const items = e.clipboardData?.items;
    if (!items) return;
    for (const item of items) {
      if (item.type.startsWith("image/")) {
        const file = item.getAsFile();
        if (file) {
          e.preventDefault();
          void processScreenshotForTab(activeShotTab, file);
          return;
        }
      }
    }
  };

  const updateManualMetricRow = (
    tab: "opponent" | "me",
    cat: string,
    nextMetric: CategoryMetric | null
  ) => {
    const updater = (prev: Record<string, CategoryMetric>) => {
      const copy = { ...prev };
      if (!nextMetric) {
        delete copy[cat];
      } else {
        copy[cat] = nextMetric;
      }
      return copy;
    };
    if (tab === "opponent") setManualOppMetrics(updater);
    else setManualMyMetrics(updater);
  };

  const handleSubmitDefense = async (e: FormEvent) => {
    e.preventDefault();
    if (slotCats.some((c) => !c)) {
      setError("Please choose a category for all 6 questions.");
      return;
    }

    if (defenseMode === "screenshot") {
      if (Object.keys(manualOppMetrics).length === 0) {
        setError("Upload or paste Opponent Stats (or fill in opponent percentages) first.");
        return;
      }
      setBusy(true);
      setError("");
      try {
        const hasAnyDiff = slotDiffs.some((d) => d !== null);
        const res = await api.recommendDefenseManual({
          categories: slotCats,
          opponent_metrics: manualOppMetrics,
          player_metrics:
            Object.keys(manualMyMetrics).length > 0 ? manualMyMetrics : undefined,
          difficulties: hasAnyDiff ? slotDiffs : undefined,
        });
        setRecs(res.recommendations);
        setDefenseMeta({
          mode: res.mode,
          expectedOpponentPoints: res.expected_opponent_points,
        });
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed computing defense.");
      } finally {
        setBusy(false);
      }
      return;
    }

    if (!opponentInput) {
      setError("Please enter an opponent username.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const hasAnyDiff = slotDiffs.some((d) => d !== null);
      const res = await api.recommendDefense({
        opponent: opponentInput,
        opponent_profile_id: p1Profile?.opponents[opponentInput],
        player: p1Input.trim() || undefined,
        player_profile_id: p1Profile?.profile_id,
        categories: slotCats,
        difficulties: hasAnyDiff ? slotDiffs : undefined,
      });
      setRecs(res.recommendations);
      setDefenseMeta({
        mode: res.mode,
        expectedOpponentPoints: res.expected_opponent_points,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed computing defense.");
    } finally {
      setBusy(false);
    }
  };

  const filteredHistory = useMemo(() => {
    if (!oppProfile) return [];
    const needle = qSearch.trim().toLowerCase();
    return Object.entries(oppProfile.question_history)
      .filter(([, v]) => {
        const catOk =
          qCategory === "ALL" ||
          v.question_category.toUpperCase() === qCategory.toUpperCase();
        const txtOk = !needle || v.question.toLowerCase().includes(needle);
        return catOk && txtOk;
      })
      .sort((a, b) => b[0].localeCompare(a[0]));
  }, [oppProfile, qSearch, qCategory]);

  const correctHistoryCount = useMemo(
    () => filteredHistory.filter(([, v]) => v.correct).length,
    [filteredHistory]
  );

  const inspectQcodes = async (qcodes: string[]) => {
    if (qcodes.length === 0 || !oppProfile) return;
    const loaded: InspectedQuestion[] = await Promise.all(
      qcodes.slice(0, 18).map(async (qc) => {
        const hist = oppProfile.question_history[qc];
        try {
          const qData = await api.getQuestion(qc);
          return {
            qcode: qc,
            questionData: qData,
            correct: hist?.correct,
            llUrl: hist?.url,
          };
        } catch {
          return {
            qcode: qc,
            fallbackText: hist?.question,
            correct: hist?.correct,
            llUrl: hist?.url,
          };
        }
      })
    );
    setInspected(loaded);
  };

  const oppCount = Object.keys(manualOppMetrics).length;
  const myCount = Object.keys(manualMyMetrics).length;
  const hasAnyRatedDiff = slotDiffs.some((d) => d !== null);

  const renderStrategyForm = () => (
    <form onSubmit={handleSubmitDefense} className="ll-card p-4 space-y-3">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-base font-semibold m-0">Defense Strategy</h2>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => {
              setSlotCats(Array(6).fill(""));
              setSlotDiffs(Array(6).fill(null));
              setRecs(null);
              setDefenseMeta(null);
            }}
            className="ll-muted px-3 py-1 rounded-lg text-xs font-medium cursor-pointer"
          >
            Clear
          </button>
          <button
            type="submit"
            disabled={busy}
            className="px-3.5 py-1 rounded-lg text-xs font-medium text-white bg-blue-600 hover:bg-blue-700 cursor-pointer"
          >
            Recommend Points
          </button>
        </div>
      </div>

      {defenseMode === "screenshot" && (
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <button
            type="button"
            onClick={() => setActiveShotTab("opponent")}
            className={`px-2.5 py-1 rounded-full font-medium cursor-pointer ${
              oppCount > 0
                ? "bg-emerald-600/15 text-emerald-700 dark:text-emerald-300"
                : "bg-amber-600/15 text-amber-700 dark:text-amber-300"
            }`}
          >
            Opponent Stats: {oppCount}/{categories.length}
          </button>
          <button
            type="button"
            onClick={() => setActiveShotTab("me")}
            className={`px-2.5 py-1 rounded-full font-medium cursor-pointer ${
              myCount > 0
                ? "bg-blue-600/15 text-blue-700 dark:text-blue-300"
                : "ll-muted"
            }`}
          >
            My Stats: {myCount}/{categories.length}
          </button>
          {shotPreviews.questions && (
            <button
              type="button"
              onClick={() => setActiveShotTab("questions")}
              className="px-2.5 py-1 rounded-full font-medium bg-indigo-600/15 text-indigo-700 dark:text-indigo-300 cursor-pointer"
            >
              Questions Shot Loaded
            </button>
          )}
        </div>
      )}

      {defenseMode === "screenshot" && hasAnyRatedDiff && myCount === 0 && (
        <p className="text-xs m-0" style={{ color: "var(--text-secondary)" }}>
          Tip: add My Stats (saved locally) to calibrate your perceived difficulty against
          your own category strengths; using a neutral 50% baseline without it.
        </p>
      )}

      <div
        className="flex flex-wrap items-center justify-between gap-2 text-xs px-1"
        style={{ color: "var(--text-secondary)" }}
      >
        <span>
          My Diff (optional): 1 Gimme (90%) · 2 Easy (75%) · 3 Med (50%) · 4 Hard (25%) · 5 Stump (10%)
        </span>
      </div>

      <div className="overflow-x-auto">
        <div className="space-y-2 text-sm min-w-[520px]">
          <div
            className="grid grid-cols-[2.25rem_minmax(0,1fr)_auto_2.75rem_3.75rem_3.75rem] gap-2 text-xs font-semibold px-1"
            style={{ color: "var(--text-secondary)" }}
          >
            <span>Slot</span>
            <span>Category</span>
            <span className="text-center">My Diff (1–5)</span>
            <span className="text-center">Rec Pts</span>
            <span className="text-right">Est Opp %</span>
            <span className="text-right">Truth %</span>
          </div>
          {slotCats.map((catVal, idx) => {
            const rec = recs?.[idx];
            const activeDiff = slotDiffs[idx];
            return (
              <div
                key={idx}
                className="grid grid-cols-[2.25rem_minmax(0,1fr)_auto_2.75rem_3.75rem_3.75rem] gap-2 items-center"
              >
                <span className="font-mono font-semibold">Q{idx + 1}</span>
                <select
                  aria-label={`Question ${idx + 1} category`}
                  value={catVal}
                  onChange={(e) => {
                    const next = [...slotCats];
                    next[idx] = e.target.value;
                    setSlotCats(next);
                  }}
                  className="ll-input w-full min-w-0"
                >
                  <option value="">Select Category...</option>
                  {categories.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
                <div
                  className="inline-flex items-center gap-0.5"
                  role="group"
                  aria-label={`Question ${idx + 1} perceived difficulty`}
                >
                  {DIFFICULTY_LEVELS.map((lvl) => {
                    const isActive = activeDiff === lvl.value;
                    return (
                      <button
                        key={lvl.value}
                        type="button"
                        title={lvl.title}
                        aria-label={`Q${idx + 1} ${lvl.title}`}
                        aria-pressed={isActive}
                        onClick={() => {
                          const next = [...slotDiffs];
                          next[idx] = isActive ? null : lvl.value;
                          setSlotDiffs(next);
                        }}
                        className={`w-6 h-7 rounded text-xs font-mono font-semibold cursor-pointer transition-colors border ${
                          isActive
                            ? "bg-blue-600 text-white border-blue-600"
                            : "ll-muted hover:bg-slate-500/15"
                        }`}
                      >
                        {lvl.label}
                      </button>
                    );
                  })}
                </div>
                <span className="text-center font-mono font-bold text-base">
                  {rec ? rec.recommended_points : "--"}
                </span>
                <span className="text-right font-mono text-xs">
                  {rec ? `${rec.estimated_opponent_pct.toFixed(1)}%` : "--"}
                </span>
                <span
                  className="text-right font-mono text-xs"
                  style={{ color: "var(--text-secondary)" }}
                >
                  {rec && rec.estimated_ground_truth_pct !== null
                    ? `${rec.estimated_ground_truth_pct.toFixed(1)}%`
                    : "--"}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {defenseMeta && (
        <div
          className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t text-xs"
          style={{ borderColor: "var(--border-subtle)" }}
        >
          <span
            className={`px-2.5 py-0.5 rounded-full font-semibold ${
              defenseMeta.mode === "irt"
                ? "bg-blue-600/15 text-blue-700 dark:text-blue-300"
                : "ll-muted"
            }`}
          >
            {defenseMeta.mode === "irt" ? "IRT Model" : "Category-Only"}
          </span>
          <span className="font-mono font-semibold">
            Expected Opp Pts: {defenseMeta.expectedOpponentPoints.toFixed(2)} / 9
          </span>
        </div>
      )}
    </form>
  );

  const renderModeSwitcher = () => (
    <section className="ll-card p-3 flex flex-wrap items-center justify-between gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => {
            setDefenseMode("screenshot");
            setError("");
          }}
          className={`px-3 py-1.5 rounded-lg text-xs font-semibold inline-flex items-center gap-1.5 cursor-pointer transition-colors ${
            defenseMode === "screenshot"
              ? "bg-blue-600 text-white"
              : "ll-muted hover:bg-slate-500/15"
          }`}
        >
          <Camera className="w-3.5 h-3.5" aria-hidden="true" />
          Screenshot / Offline Mode
        </button>
        <button
          type="button"
          onClick={() => {
            setDefenseMode("live");
            setError("");
          }}
          className={`px-3 py-1.5 rounded-lg text-xs font-semibold inline-flex items-center gap-1.5 cursor-pointer transition-colors ${
            defenseMode === "live"
              ? "bg-blue-600 text-white"
              : "ll-muted hover:bg-slate-500/15"
          }`}
        >
          <Shield className="w-3.5 h-3.5" aria-hidden="true" />
          Live LL Profile Mode
        </button>
      </div>
      <span className="text-xs" style={{ color: "var(--text-secondary)" }}>
        {defenseMode === "screenshot"
          ? "No login required — paste or upload screenshots & run IRT defense"
          : auth.authenticated
            ? `Signed in as ${auth.formatted_username || auth.username}`
            : "Requires LearnedLeague sign-in"}
      </span>
    </section>
  );

  const activeStatsTab: "opponent" | "me" | null =
    activeShotTab === "questions" ? null : activeShotTab;
  const activeMetricsMap =
    activeStatsTab === "opponent" ? manualOppMetrics : manualMyMetrics;
  const activeOcr = activeStatsTab ? ocrStatus[activeStatsTab] : null;
  const activePreview = shotPreviews[activeShotTab];

  if (defenseMode === "screenshot") {
    return (
      <div className="space-y-4">
        {renderModeSwitcher()}

        {error && (
          <div className="ll-card p-3">
            <p role="alert" className="text-sm text-red-600 dark:text-red-400 m-0">
              {error}
            </p>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 items-start">
          {renderStrategyForm()}

          {/* Right Card: Screenshots & Parsed Stats */}
          <section className="ll-card p-4 space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-base font-semibold m-0">
                Screenshots &amp; Parsed Stats
              </h2>
              <div className="flex gap-1" role="tablist" aria-label="Screenshot source">
                {(
                  [
                    { id: "opponent", label: `Opponent (${oppCount})` },
                    { id: "me", label: `My Stats (${myCount})` },
                    { id: "questions", label: "Questions Shot" },
                  ] as { id: ShotTab; label: string }[]
                ).map((tab) => (
                  <button
                    key={tab.id}
                    type="button"
                    role="tab"
                    aria-selected={activeShotTab === tab.id}
                    onClick={() => setActiveShotTab(tab.id)}
                    className={`ll-tab-btn px-2.5 py-1.5 text-xs font-semibold cursor-pointer rounded-t-md ${
                      activeShotTab === tab.id
                        ? "bg-blue-600/10"
                        : "hover:bg-slate-500/10"
                    }`}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>
            </div>

            <div
              onDragOver={(e) => e.preventDefault()}
              onDrop={handleDropScreenshot}
              onPaste={handlePasteZone}
              tabIndex={0}
              className="ll-muted rounded-xl p-4 text-center space-y-2 border-dashed border-2"
            >
              <div className="flex flex-wrap items-center justify-center gap-2 text-xs">
                <ClipboardPaste className="w-4 h-4 opacity-75" aria-hidden="true" />
                <span>
                  Press <strong>Cmd+V / Ctrl+V</strong> anywhere, drag-and-drop, or upload
                  a screenshot for{" "}
                  <strong>
                    {activeShotTab === "opponent"
                      ? "Opponent Stats"
                      : activeShotTab === "me"
                        ? "My Stats"
                        : "Today's Questions"}
                  </strong>
                </span>
              </div>
              <div className="flex flex-wrap items-center justify-center gap-2">
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  aria-label="Upload screenshot image"
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) {
                      void processScreenshotForTab(activeShotTab, file);
                    }
                    e.target.value = "";
                  }}
                  className="hidden"
                />
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="px-3 py-1.5 rounded-lg text-xs font-medium text-white bg-blue-600 hover:bg-blue-700 inline-flex items-center gap-1.5 cursor-pointer"
                >
                  <Upload className="w-3.5 h-3.5" aria-hidden="true" />
                  Choose Image
                </button>
                {activePreview && (
                  <>
                    <button
                      type="button"
                      onClick={() =>
                        setScreenshotLightbox({
                          url: activePreview,
                          title:
                            activeShotTab === "opponent"
                              ? "Opponent Stats Screenshot"
                              : activeShotTab === "me"
                                ? "My Stats Screenshot"
                                : "Questions Screenshot",
                        })
                      }
                      className="ll-card px-2.5 py-1.5 rounded-lg text-xs font-medium inline-flex items-center gap-1 cursor-pointer"
                    >
                      <ZoomIn className="w-3.5 h-3.5" aria-hidden="true" />
                      Enlarge
                    </button>
                    <button
                      type="button"
                      onClick={() =>
                        setShotPreviews((prev) => ({ ...prev, [activeShotTab]: null }))
                      }
                      className="ll-card px-2.5 py-1.5 rounded-lg text-xs font-medium inline-flex items-center gap-1 cursor-pointer text-red-600 dark:text-red-400"
                    >
                      <Trash2 className="w-3.5 h-3.5" aria-hidden="true" />
                      Remove Image
                    </button>
                  </>
                )}
              </div>
            </div>

            {activePreview && (
              <div
                className="border rounded-lg overflow-hidden cursor-zoom-in"
                style={{ borderColor: "var(--border-subtle)" }}
                onClick={() =>
                  setScreenshotLightbox({
                    url: activePreview,
                    title:
                      activeShotTab === "opponent"
                        ? "Opponent Stats Screenshot"
                        : activeShotTab === "me"
                          ? "My Stats Screenshot"
                          : "Questions Screenshot",
                  })
                }
              >
                <img
                  src={activePreview}
                  alt={`${activeShotTab} screenshot preview`}
                  className={`w-full object-contain bg-black/5 ${
                    activeShotTab === "questions" ? "max-h-[460px]" : "max-h-48"
                  }`}
                />
              </div>
            )}

            {activeStatsTab && activeOcr && (
              <div className="space-y-2">
                <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
                  <div className="flex flex-wrap items-center gap-2">
                    {activeOcr.loading ? (
                      <span className="font-medium text-blue-600 dark:text-blue-400">
                        Running local OCR...
                      </span>
                    ) : activeOcr.matched !== null ? (
                      <span
                        className={`px-2.5 py-0.5 rounded-full font-semibold ${
                          activeOcr.matched >= 15
                            ? "bg-emerald-600/15 text-emerald-700 dark:text-emerald-300"
                            : "bg-amber-600/15 text-amber-700 dark:text-amber-300"
                        }`}
                      >
                        {activeOcr.matched}/{categories.length} categories parsed
                      </span>
                    ) : (
                      <span style={{ color: "var(--text-secondary)" }}>
                        {activeStatsTab === "me"
                          ? "Saved locally across sessions once parsed or entered."
                          : "Upload or paste your opponent's category stats table."}
                      </span>
                    )}
                  </div>

                  <div className="flex flex-wrap gap-1.5">
                    <button
                      type="button"
                      onClick={() =>
                        setShowTextFallback((prev) => ({
                          ...prev,
                          [activeStatsTab]: !prev[activeStatsTab],
                        }))
                      }
                      className="ll-muted px-2.5 py-1 rounded-lg text-xs font-medium cursor-pointer"
                    >
                      {showTextFallback[activeStatsTab] ? "Hide Text Paste" : "Paste Table Text"}
                    </button>
                    <button
                      type="button"
                      onClick={() =>
                        setShowEditableTable((prev) => ({
                          ...prev,
                          [activeStatsTab]: !prev[activeStatsTab],
                        }))
                      }
                      className="ll-muted px-2.5 py-1 rounded-lg text-xs font-medium cursor-pointer"
                    >
                      {showEditableTable[activeStatsTab] ? "Hide Table" : "Edit Table"}
                    </button>
                    {Object.keys(activeMetricsMap).length > 0 && (
                      <button
                        type="button"
                        onClick={() => {
                          if (activeStatsTab === "opponent") setManualOppMetrics({});
                          else setManualMyMetrics({});
                          setOcrStatus((prev) => ({
                            ...prev,
                            [activeStatsTab]: EMPTY_OCR_STATUS,
                          }));
                        }}
                        className="ll-muted px-2.5 py-1 rounded-lg text-xs font-medium text-red-600 dark:text-red-400 cursor-pointer"
                      >
                        Clear Stats
                      </button>
                    )}
                  </div>
                </div>

                {activeOcr.error && (
                  <p role="alert" className="text-xs text-red-600 dark:text-red-400 m-0">
                    {activeOcr.error}
                  </p>
                )}

                {activeOcr.missing.length > 0 && activeOcr.matched !== null && activeOcr.matched > 0 && (
                  <p className="text-xs m-0" style={{ color: "var(--text-secondary)" }}>
                    Missing: {activeOcr.missing.join(", ")}
                  </p>
                )}

                {showTextFallback[activeStatsTab] && (
                  <div className="space-y-2 p-2.5 rounded-lg ll-muted">
                    <textarea
                      rows={5}
                      value={textFallbackInput[activeStatsTab]}
                      onChange={(e) =>
                        setTextFallbackInput((prev) => ({
                          ...prev,
                          [activeStatsTab]: e.target.value,
                        }))
                      }
                      placeholder={"AMER HIST 15-20 .750\nART 10-18 .556\nBUS/ECON 12-20 .600"}
                      className="ll-input w-full font-mono text-xs"
                    />
                    <div className="flex justify-end">
                      <button
                        type="button"
                        disabled={activeOcr.loading}
                        onClick={() => void handleParseTextFallback(activeStatsTab)}
                        className="px-3 py-1 rounded-lg text-xs font-medium text-white bg-blue-600 hover:bg-blue-700 cursor-pointer"
                      >
                        Parse Text
                      </button>
                    </div>
                  </div>
                )}

                {showEditableTable[activeStatsTab] && (
                  <div
                    className="max-h-[320px] overflow-y-auto border rounded-lg text-xs"
                    style={{ borderColor: "var(--border-subtle)" }}
                  >
                    <table className="w-full border-collapse">
                      <thead
                        className="sticky top-0 ll-muted text-left"
                        style={{ color: "var(--text-secondary)" }}
                      >
                        <tr>
                          <th className="px-2.5 py-1.5 font-semibold">Category</th>
                          <th className="px-2 py-1.5 font-semibold w-20">Correct</th>
                          <th className="px-2 py-1.5 font-semibold w-20">Total</th>
                          <th className="px-2.5 py-1.5 font-semibold w-24 text-right">%</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y" style={{ borderColor: "var(--border-subtle)" }}>
                        {categories.map((cat) => {
                          const m = activeMetricsMap[cat];
                          const pctVal = m ? (m.percent * 100).toFixed(1) : "";
                          return (
                            <tr key={cat} style={{ borderColor: "var(--border-subtle)" }}>
                              <td className="px-2.5 py-1 font-medium">{cat}</td>
                              <td className="px-2 py-1">
                                <input
                                  type="number"
                                  min={0}
                                  aria-label={`${cat} correct`}
                                  value={m ? m.correct : ""}
                                  placeholder="0"
                                  onChange={(e) => {
                                    const val = Math.max(0, Number(e.target.value) || 0);
                                    const tot = m?.total ?? 0;
                                    if (val === 0 && tot === 0 && !m) return;
                                    const pct =
                                      tot > 0 ? Math.min(1, val / tot) : (m?.percent ?? 0);
                                    updateManualMetricRow(activeStatsTab, cat, {
                                      correct: val,
                                      total: tot,
                                      percent: Number(pct.toFixed(6)),
                                    });
                                  }}
                                  className="ll-input w-full py-0.5 px-1.5 text-xs font-mono"
                                />
                              </td>
                              <td className="px-2 py-1">
                                <input
                                  type="number"
                                  min={0}
                                  aria-label={`${cat} total`}
                                  value={m ? m.total : ""}
                                  placeholder="0"
                                  onChange={(e) => {
                                    const tot = Math.max(0, Number(e.target.value) || 0);
                                    const corr = m?.correct ?? 0;
                                    if (corr === 0 && tot === 0) {
                                      updateManualMetricRow(activeStatsTab, cat, null);
                                      return;
                                    }
                                    const pct = tot > 0 ? Math.min(1, corr / tot) : 0;
                                    updateManualMetricRow(activeStatsTab, cat, {
                                      correct: corr,
                                      total: tot,
                                      percent: Number(pct.toFixed(6)),
                                    });
                                  }}
                                  className="ll-input w-full py-0.5 px-1.5 text-xs font-mono"
                                />
                              </td>
                              <td className="px-2.5 py-1 text-right">
                                <input
                                  type="number"
                                  min={0}
                                  max={100}
                                  step={0.1}
                                  aria-label={`${cat} percent`}
                                  value={pctVal}
                                  placeholder="--"
                                  onChange={(e) => {
                                    const rawStr = e.target.value;
                                    if (rawStr === "") {
                                      updateManualMetricRow(activeStatsTab, cat, null);
                                      return;
                                    }
                                    const num = Math.min(100, Math.max(0, Number(rawStr) || 0));
                                    updateManualMetricRow(activeStatsTab, cat, {
                                      correct: 0,
                                      total: 0,
                                      percent: Number((num / 100).toFixed(6)),
                                    });
                                  }}
                                  className="ll-input w-full py-0.5 px-1.5 text-xs font-mono text-right"
                                />
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}
          </section>
        </div>

        <ModalDialog
          open={Boolean(screenshotLightbox)}
          onClose={() => setScreenshotLightbox(null)}
          title={screenshotLightbox?.title || "Screenshot Preview"}
          wide
        >
          {screenshotLightbox && (
            <div className="flex justify-center">
              <img
                src={screenshotLightbox.url}
                alt={screenshotLightbox.title}
                className="max-w-full max-h-[75vh] rounded-lg object-contain"
              />
            </div>
          )}
        </ModalDialog>
      </div>
    );
  }

  if (!auth.authenticated) {
    return (
      <div className="space-y-4">
        {renderModeSwitcher()}
        <div className="ll-card p-8 text-center space-y-3">
          <Shield className="w-8 h-8 mx-auto opacity-60" aria-hidden="true" />
          <h1 className="text-lg font-semibold m-0">LearnedLeague Login Required</h1>
          <p className="text-sm m-0" style={{ color: "var(--text-secondary)" }}>
            Sign in with your LearnedLeague account to fetch live profiles, HUN
            similarity, Radar charts, and Today&apos;s Questions — or switch to{" "}
            <strong>Screenshot / Offline Mode</strong> above without logging in.
          </p>
          <div className="flex flex-wrap items-center justify-center gap-2">
            <button
              type="button"
              onClick={onRequireLogin}
              className="px-4 min-h-10 rounded-lg text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 cursor-pointer"
            >
              Sign In to LearnedLeague
            </button>
            <button
              type="button"
              onClick={() => setDefenseMode("screenshot")}
              className="ll-muted px-4 min-h-10 rounded-lg text-sm font-medium cursor-pointer"
            >
              Use Screenshot Mode
            </button>
          </div>
        </div>
      </div>
    );
  }

  const opponentChoices = p1Profile ? Object.keys(p1Profile.opponents) : [];
  const scheduleByName = new Map(
    (p1Profile?.opponent_schedule ?? []).map((item) => [
      item.username.toLowerCase(),
      item,
    ])
  );
  const firstUnplayedSched = (p1Profile?.opponent_schedule ?? []).find(
    (item) => item.played === false
  );
  const firstUpcomingDay = firstUnplayedSched
    ? firstUnplayedSched.match_day
    : currentDay + 1;

  const trimmedOpp = opponentInput.trim();
  const selectedOppIdx = opponentChoices.findIndex(
    (o) => o.toLowerCase() === trimmedOpp.toLowerCase()
  );
  const selectedOppSched = scheduleByName.get(trimmedOpp.toLowerCase());
  const selectedOppDay =
    selectedOppSched?.match_day ?? (selectedOppIdx >= 0 ? selectedOppIdx + 1 : null);
  const selectedOppIsPast =
    selectedOppDay !== null &&
    (selectedOppSched?.played !== null && selectedOppSched?.played !== undefined
      ? selectedOppSched.played
      : selectedOppDay <= currentDay);
  const targetQuestionsDay =
    selectedOppIsPast && selectedOppDay !== null ? selectedOppDay : currentDay + 1;

  return (
    <div className="space-y-4">
      {renderModeSwitcher()}

      {/* Player & Action Header */}
      <section className="ll-card p-4 space-y-3">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
          <div>
            <label htmlFor="def-p1" className="block text-xs font-medium mb-1">
              You (Player 1)
            </label>
            <div className="flex gap-2">
              <input
                id="def-p1"
                type="text"
                value={p1Input}
                onChange={(e) => setP1Input(e.target.value)}
                className="ll-input flex-1"
              />
              <button
                type="button"
                disabled={busy}
                onClick={() => void loadPlayer1(p1Input, true)}
                className="ll-muted px-3 rounded-lg text-xs font-medium inline-flex items-center gap-1 cursor-pointer"
              >
                <Users className="w-3.5 h-3.5" aria-hidden="true" />
                Load Opponents
              </button>
            </div>
          </div>

          <div>
            <label htmlFor="def-opp" className="block text-xs font-medium mb-1">
              Opponent
            </label>
            <div className="flex gap-2">
              <div ref={oppComboRef} className="relative flex-1">
                <input
                  id="def-opp"
                  type="text"
                  role="combobox"
                  aria-expanded={oppMenuOpen}
                  aria-autocomplete="none"
                  value={opponentInput}
                  onChange={(e) => setOpponentInput(e.target.value)}
                  onFocus={() => {
                    if (opponentChoices.length > 0) setOppMenuOpen(true);
                  }}
                  onClick={() => {
                    if (opponentChoices.length > 0) setOppMenuOpen(true);
                  }}
                  onKeyDown={(e) => {
                    if (e.key === "Escape") {
                      setOppMenuOpen(false);
                    } else if (e.key === "Enter") {
                      e.preventDefault();
                      setOppMenuOpen(false);
                      void loadOpponent(opponentInput);
                    }
                  }}
                  className="ll-input w-full pr-8"
                />
                {opponentChoices.length > 0 && (
                  <button
                    type="button"
                    aria-label="Toggle opponent list"
                    aria-expanded={oppMenuOpen}
                    onClick={() => setOppMenuOpen((v) => !v)}
                    className="absolute right-1.5 top-1/2 -translate-y-1/2 p-1 rounded hover:bg-slate-500/15 cursor-pointer"
                    style={{ color: "var(--text-secondary)" }}
                  >
                    <ChevronDown className="w-4 h-4" aria-hidden="true" />
                  </button>
                )}
                {oppMenuOpen && opponentChoices.length > 0 && (
                  <ul
                    role="listbox"
                    aria-label="Opponents"
                    className="absolute left-0 right-0 top-full mt-1 max-h-64 overflow-y-auto ll-card shadow-lg z-30 py-1 text-sm divide-y"
                    style={{ borderColor: "var(--border-subtle)" }}
                  >
                    {opponentChoices.map((o, idx) => {
                      const isSelected =
                        o.toLowerCase() === opponentInput.trim().toLowerCase();
                      const sched = scheduleByName.get(o.toLowerCase());
                      const matchDay = sched?.match_day ?? idx + 1;
                      const isPlayed =
                        sched?.played !== null && sched?.played !== undefined
                          ? sched.played
                          : matchDay <= currentDay;
                      const isNext = !isPlayed && matchDay === firstUpcomingDay;
                      const statusNote = isPlayed
                        ? `MD ${matchDay} · Played${sched?.result ? ` (${sched.result})` : ""}`
                        : isNext
                          ? `MD ${matchDay} · Up next`
                          : `MD ${matchDay} · Upcoming`;
                      const noteClass = isPlayed
                        ? ""
                        : isNext
                          ? "text-blue-600 dark:text-blue-400 font-medium"
                          : "text-emerald-600 dark:text-emerald-400";
                      return (
                        <li key={o} style={{ borderColor: "var(--border-subtle)" }}>
                          <button
                            type="button"
                            role="option"
                            aria-selected={isSelected}
                            onClick={() => {
                              setOpponentInput(o);
                              setOppMenuOpen(false);
                              void loadOpponent(o);
                            }}
                            className={`w-full text-left px-3 py-1.5 flex items-center justify-between gap-2 cursor-pointer transition-colors ${
                              isSelected
                                ? "bg-blue-600/15 text-blue-700 dark:text-blue-300 font-semibold"
                                : "hover:bg-slate-500/10"
                            }`}
                          >
                            <span className="truncate">{o}</span>
                            <span
                              className={`text-xs font-normal shrink-0 ${noteClass}`}
                              style={
                                isPlayed ? { color: "var(--text-secondary)" } : undefined
                              }
                            >
                              {statusNote}
                            </span>
                          </button>
                        </li>
                      );
                    })}
                  </ul>
                )}
              </div>
              <button
                type="button"
                disabled={busy}
                onClick={() => {
                  setOppMenuOpen(false);
                  void loadOpponent(opponentInput, true);
                }}
                title="Refresh opponent from LearnedLeague"
                className="ll-muted px-3 rounded-lg text-xs font-medium inline-flex items-center gap-1 cursor-pointer"
              >
                <RefreshCw className="w-3.5 h-3.5" aria-hidden="true" />
                Refresh
              </button>
            </div>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2 pt-1">
          <button
            type="button"
            disabled={busy}
            onClick={() => void handleCalculateHun()}
            className="ll-muted px-3 py-1.5 rounded-lg text-xs font-medium inline-flex items-center gap-1.5 cursor-pointer"
          >
            <Activity className="w-3.5 h-3.5" aria-hidden="true" />
            Calculate HUN
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={() => void handleShowSimilarity()}
            className="ll-muted px-3 py-1.5 rounded-lg text-xs font-medium cursor-pointer"
          >
            Show Similarity Radar
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={async () => {
              if (!oppProfile || oppProfile.formatted_username.toLowerCase() !== opponentInput.toLowerCase()) {
                await loadOpponent(opponentInput);
              }
              setShowMetrics(true);
            }}
            className="ll-muted px-3 py-1.5 rounded-lg text-xs font-medium inline-flex items-center gap-1.5 cursor-pointer"
          >
            <BarChart3 className="w-3.5 h-3.5" aria-hidden="true" />
            Opponent Category Metrics
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={() =>
              void handleOpenTodaysQuestions(todaysModal.showAnswers, targetQuestionsDay)
            }
            title={
              selectedOppIsPast && selectedOppDay !== null
                ? `View LL ${latestSeason} MD ${selectedOppDay} questions vs ${trimmedOpp}`
                : "View Today's Questions"
            }
            className="px-3 py-1.5 rounded-lg text-xs font-medium text-white bg-indigo-600 hover:bg-indigo-700 inline-flex items-center gap-1.5 cursor-pointer"
          >
            <CalendarClock className="w-3.5 h-3.5" aria-hidden="true" />
            {selectedOppIsPast && selectedOppDay !== null
              ? `MD ${selectedOppDay} Questions`
              : "Today's Questions"}
          </button>
          <label className="inline-flex items-center gap-1.5 text-xs cursor-pointer">
            <input
              type="checkbox"
              checked={todaysModal.showAnswers}
              onChange={(e) =>
                setTodaysModal((prev) => ({
                  ...prev,
                  showAnswers: e.target.checked,
                }))
              }
            />
            Display Submitted Answers
          </label>

          {hunResult && (
            <span className="ml-auto text-xs font-mono px-3 py-1 rounded-full bg-blue-600/15 text-blue-700 dark:text-blue-300 font-semibold">
              HUN Similarity: {hunResult.score.toFixed(3)} ({hunResult.matching_outcomes}/
              {hunResult.shared_questions} shared)
            </span>
          )}
        </div>

        {error && (
          <p role="alert" className="text-sm text-red-600 dark:text-red-400">
            {error}
          </p>
        )}
      </section>

      {/* Main Split: Defense Strategy & Question History */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {renderStrategyForm()}

        <section className="ll-card p-4 space-y-3 flex flex-col">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-base font-semibold m-0">
              Opponent History ({oppProfile?.formatted_username || opponentInput || "--"})
            </h2>
            <span className="text-xs font-mono font-semibold">
              Correct: {correctHistoryCount}/{filteredHistory.length}
            </span>
          </div>

          <div className="flex flex-wrap gap-2 text-sm">
            <input
              type="search"
              aria-label="Search opponent question history"
              value={qSearch}
              onChange={(e) => setQSearch(e.target.value)}
              placeholder="Search question text..."
              className="ll-input flex-1 min-w-[160px]"
            />
            <select
              aria-label="Filter opponent history category"
              value={qCategory}
              onChange={(e) => setQCategory(e.target.value)}
              className="ll-input"
            >
              <option value="ALL">ALL</option>
              {categories.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
            <button
              type="button"
              disabled={Object.values(selectedQcodes).filter(Boolean).length === 0}
              onClick={() =>
                void inspectQcodes(
                  Object.keys(selectedQcodes).filter((k) => selectedQcodes[k])
                )
              }
              className="ll-muted px-3 py-1.5 rounded-lg text-xs font-medium disabled:opacity-40 cursor-pointer"
            >
              Open Selected
            </button>
          </div>

          <div
            className="flex-1 max-h-[340px] overflow-y-auto border rounded-lg divide-y text-sm"
            style={{ borderColor: "var(--border-subtle)" }}
          >
            {filteredHistory.slice(0, 200).map(([qcode, item]) => (
              <div
                key={qcode}
                className="flex items-center justify-between gap-2 px-3 py-2 hover:bg-slate-500/5"
                style={{ borderColor: "var(--border-subtle)" }}
              >
                <label className="flex items-center gap-2 min-w-0 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={Boolean(selectedQcodes[qcode])}
                    onChange={(e) =>
                      setSelectedQcodes({
                        ...selectedQcodes,
                        [qcode]: e.target.checked,
                      })
                    }
                  />
                  <span className="font-mono text-xs font-semibold shrink-0">
                    {qcode}
                  </span>
                  <span className="text-xs truncate" style={{ color: "var(--text-secondary)" }}>
                    {item.question_category}
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
      </div>

      {/* Similarity Radar Modal */}
      <ModalDialog
        open={radarData.open}
        onClose={() => setRadarData((prev) => ({ ...prev, open: false }))}
        title={`Category Similarity: ${radarData.player1} vs ${radarData.player2}`}
        wide
      >
        <RadarChart
          player1={radarData.player1}
          player2={radarData.player2}
          series={radarData.series}
        />
      </ModalDialog>

      {/* Opponent Category Metrics Modal */}
      {oppProfile && (
        <CategoryMetricsModal
          open={showMetrics}
          onClose={() => setShowMetrics(false)}
          username={oppProfile.formatted_username}
          metrics={oppProfile.category_metrics}
        />
      )}

      {/* Match Day Questions Modal */}
      <ModalDialog
        open={todaysModal.open}
        onClose={() => setTodaysModal((prev) => ({ ...prev, open: false }))}
        title={
          todaysModal.data?.message ||
          (selectedOppIsPast && selectedOppDay !== null
            ? `LL ${latestSeason} MD ${selectedOppDay} Questions`
            : "Today's Questions")
        }
        wide
      >
        {todaysModal.loading ? (
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            Loading Match Day Questions from LearnedLeague...
          </p>
        ) : todaysModal.data && todaysModal.data.questions.length === 0 ? (
          <p className="text-sm">{todaysModal.data.message}</p>
        ) : (
          <div className="space-y-3">
            {todaysModal.data?.questions.map((q) => (
              <div key={q.id} className="ll-muted p-3.5 rounded-xl space-y-2">
                <div className="text-xs font-mono font-bold">Q{q.id}</div>
                <p className="text-sm leading-relaxed">{q.question}</p>
                <div className="flex flex-wrap gap-3 text-xs">
                  <span className="px-2 py-1 rounded ll-card">
                    Submitted: <strong>{q.submitted_answer}</strong>
                  </span>
                  <span className="px-2 py-1 rounded ll-card">
                    {q.points_assigned.endsWith("%") ? "League %:" : "Pts Assigned:"}{" "}
                    <strong>{q.points_assigned}</strong>
                  </span>
                  <span className="px-2 py-1 rounded ll-card">
                    Correct Answer: <strong>{q.correct_answer}</strong>
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </ModalDialog>

      <QuestionDrawer
        items={inspected}
        onClose={() => setInspected([])}
        onOpenImage={setLightboxUrl}
      />
      <ImageLightbox imageUrl={lightboxUrl} onClose={() => setLightboxUrl(null)} />
    </div>
  );
}

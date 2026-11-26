import {
  extFetchText,
  getCachedExtProfile,
  getExtensionAuth,
  isExtensionAuthActive,
  setCachedExtProfile,
} from "./extensionBridge";
import type {
  AppMeta,
  AuthMe,
  CategoryMetric,
  DefenseRecommendResponse,
  GradeResponse,
  LuckAnalysisResponse,
  ManualDefenseRecommendResponse,
  MiniLeagueCatalogItem,
  MiniLeagueDetail,
  MockDayPayload,
  OneDayCatalogItem,
  OneDayDetail,
  ParseStatsScreenshotResponse,
  PlayerProfile,
  QuestionsResponse,
  QuestionItem,
  RadarPoint,
  TodaysQuestionsResponse,
} from "../types";

export class ApiError extends Error {
  status: number;
  code: string | null;

  constructor(message: string, status: number, code: string | null = null) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

type AuthHandler = (code: "LL_AUTH_REQUIRED" | "ACCESS_GATE_REQUIRED") => void;
let onAuthEvent: AuthHandler | null = null;

export function setAuthEventHandler(handler: AuthHandler | null): void {
  onAuthEvent = handler;
}

export async function apiFetch<T>(url: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(url, {
    ...init,
    credentials: "include",
    headers: {
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...(init?.headers ?? {}),
    },
  });

  if (!resp.ok) {
    let detail = `Request failed (${resp.status})`;
    let code: string | null = resp.headers.get("X-LL-Error-Code");
    try {
      const data = (await resp.json()) as { detail?: string; code?: string };
      if (data.detail) detail = data.detail;
      if (data.code) code = data.code;
    } catch {
      // Ignore JSON parse error
    }
    if (resp.status === 401 && onAuthEvent) {
      onAuthEvent("LL_AUTH_REQUIRED");
    } else if (resp.status === 403 && code === "ACCESS_GATE_REQUIRED" && onAuthEvent) {
      onAuthEvent("ACCESS_GATE_REQUIRED");
    }
    throw new ApiError(detail, resp.status, code);
  }

  return (await resp.json()) as T;
}

const LL_BASE = "https://www.learnedleague.com";

async function fetchProfileViaExtension(
  identifier: string,
  profileId?: string,
  refresh = false
): Promise<PlayerProfile> {
  const lookupKey = (profileId || identifier).trim();
  const cached = getCachedExtProfile(lookupKey, refresh);
  if (cached) return cached;

  const latestHtml = await extFetchText(
    `${LL_BASE}/profiles.php?${encodeURIComponent(lookupKey)}&1`
  );
  const initial = await apiFetch<PlayerProfile>("/api/extension/parse-profile", {
    method: "POST",
    body: JSON.stringify({ latest_html: latestHtml }),
  });

  const pid = initial.profile_id;
  const [qhistHtml, statsHtml, pastHtml] = await Promise.all([
    extFetchText(`${LL_BASE}/profiles.php?${pid}&9`),
    extFetchText(`${LL_BASE}/profiles.php?${pid}&2`),
    extFetchText(`${LL_BASE}/profiles.php?${pid}&7`),
  ]);

  const fullProfile = await apiFetch<PlayerProfile>("/api/extension/parse-profile", {
    method: "POST",
    body: JSON.stringify({
      latest_html: latestHtml,
      qhist_html: qhistHtml,
      stats_html: statsHtml,
      past_html: pastHtml,
    }),
  });
  setCachedExtProfile(fullProfile);
  return fullProfile;
}

export const api = {
  getMeta: () => apiFetch<AppMeta>("/api/meta"),
  verifyGate: (code: string) =>
    apiFetch<{ unlocked: boolean }>("/api/auth/gate", {
      method: "POST",
      body: JSON.stringify({ code }),
    }),
  getAuthMe: () => apiFetch<AuthMe>("/api/auth/me"),
  login: (username: string, password: string, remember_me: boolean) =>
    apiFetch<AuthMe>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password, remember_me }),
    }),
  loginWithCookie: (cookie: string, remember_me: boolean) =>
    apiFetch<AuthMe>("/api/auth/cookie", {
      method: "POST",
      body: JSON.stringify({ cookie, remember_me }),
    }),
  startInteractiveLogin: () =>
    apiFetch<AuthMe & { status: "waiting_for_user" | "authenticated" }>(
      "/api/auth/interactive/start",
      { method: "POST" }
    ),
  getInteractiveLoginStatus: () =>
    apiFetch<AuthMe & { status: "waiting_for_user" | "authenticated" | "stopped" }>(
      "/api/auth/interactive/status"
    ),
  autoLogin: () =>
    apiFetch<AuthMe>("/api/auth/auto-login", { method: "POST" }),
  logout: (clear_keychain = true) =>
    apiFetch<{ authenticated: boolean }>(
      `/api/auth/logout?clear_keychain=${clear_keychain}`,
      { method: "POST" }
    ),
  deleteLegacyLoginFile: () =>
    apiFetch<{ deleted: boolean }>("/api/auth/legacy-login-file", {
      method: "DELETE",
    }),

  getQuestions: (params: {
    min_pct?: number;
    max_pct?: number;
    category?: string;
    season?: string;
    search?: string;
    limit?: number;
    offset?: number;
    random?: boolean;
  }) => {
    const qs = new URLSearchParams();
    if (params.min_pct !== undefined) qs.set("min_pct", String(params.min_pct));
    if (params.max_pct !== undefined) qs.set("max_pct", String(params.max_pct));
    if (params.category) qs.set("category", params.category);
    if (params.season) qs.set("season", params.season);
    if (params.search) qs.set("search", params.search);
    if (params.limit !== undefined) qs.set("limit", String(params.limit));
    if (params.offset !== undefined) qs.set("offset", String(params.offset));
    if (params.random) qs.set("random", "true");
    return apiFetch<QuestionsResponse>(`/api/questions?${qs.toString()}`);
  },
  getQuestion: (qcode: string) =>
    apiFetch<QuestionItem>(`/api/questions/${encodeURIComponent(qcode)}`),
  gradeAnswer: (submitted_answer: string, correct_answer: string) =>
    apiFetch<GradeResponse>("/api/questions/grade", {
      method: "POST",
      body: JSON.stringify({ submitted_answer, correct_answer }),
    }),
  triggerSync: () =>
    apiFetch<{ triggered: boolean }>("/api/questions/sync", { method: "POST" }),
  syncArchiveViaExtension: async (
    onProgress?: (msg: string) => void
  ): Promise<{
    syncedDays: number;
    importedQuestions: number;
    remainingDays: number;
    latestSeason: number;
    currentDay: number;
  }> => {
    onProgress?.("Checking latest season via Chrome Extension...");
    const allrundlesHtml = await extFetchText(`${LL_BASE}/allrundles.php`);
    const plan = await apiFetch<{
      latest_season: number;
      current_day: number;
      batch: { season: number; day: number }[];
      remaining_missing_days: number;
    }>("/api/extension/sync-plan", {
      method: "POST",
      body: JSON.stringify({ allrundles_html: allrundlesHtml, max_days: 25 }),
    });

    let syncedDays = 0;
    let importedQuestions = 0;
    for (let idx = 0; idx < plan.batch.length; idx++) {
      if (idx > 0) {
        const delayMs = 2500 + Math.random() * 1000;
        await new Promise((resolve) => window.setTimeout(resolve, delayMs));
      }
      const { season, day } = plan.batch[idx];
      onProgress?.(
        `Syncing LL ${season} MD ${day} (${idx + 1}/${plan.batch.length}) via Chrome Extension...`
      );
      const html = await extFetchText(`${LL_BASE}/match.php?${season}&${day}`);
      const ingested = await apiFetch<{
        season: number;
        day: number;
        imported: number;
      }>("/api/extension/ingest-matchday", {
        method: "POST",
        body: JSON.stringify({ season, day, html }),
      });
      syncedDays += 1;
      importedQuestions += ingested.imported;
    }

    return {
      syncedDays,
      importedQuestions,
      remainingDays: plan.remaining_missing_days,
      latestSeason: plan.latest_season,
      currentDay: plan.current_day,
    };
  },
  lookupTerm: (q: string) =>
    apiFetch<{ term: string; source: string; summary: string }>(
      `/api/lookup?q=${encodeURIComponent(q)}`
    ),

  getOneDays: (search = "", refresh = false) =>
    apiFetch<{ items: OneDayCatalogItem[]; total: number }>(
      `/api/onedays?search=${encodeURIComponent(search)}&refresh=${refresh}`
    ),
  getOneDayDetail: (slug: string) =>
    apiFetch<OneDayDetail>(`/api/onedays/${encodeURIComponent(slug)}`),

  getMiniLeagues: (search = "", refresh = false) =>
    apiFetch<{ items: MiniLeagueCatalogItem[]; total: number }>(
      `/api/minileagues?search=${encodeURIComponent(search)}&refresh=${refresh}`
    ),
  getMiniLeagueDetail: (slug: string) =>
    apiFetch<MiniLeagueDetail>(`/api/minileagues/${encodeURIComponent(slug)}`),

  generateMockDay: (seed: number | null, threshold: number) =>
    apiFetch<MockDayPayload>("/api/mock-day/generate", {
      method: "POST",
      body: JSON.stringify({ seed, threshold }),
    }),

  getMyProfile: async (refresh = false) => {
    if (isExtensionAuthActive()) {
      const extAuth = getExtensionAuth();
      if (!extAuth?.username && !extAuth?.profile_id) {
        throw new ApiError("Chrome extension session not connected.", 401, "LL_AUTH_REQUIRED");
      }
      return fetchProfileViaExtension(
        extAuth.username || extAuth.profile_id || "",
        extAuth.profile_id || undefined,
        refresh
      );
    }
    return apiFetch<PlayerProfile>(`/api/players/me?refresh=${refresh}`);
  },
  getPlayerProfile: async (identifier: string, profileId?: string, refresh = false) => {
    if (isExtensionAuthActive()) {
      return fetchProfileViaExtension(identifier, profileId, refresh);
    }
    const qs = new URLSearchParams();
    if (profileId) qs.set("profile_id", profileId);
    if (refresh) qs.set("refresh", "true");
    return apiFetch<PlayerProfile>(
      `/api/players/${encodeURIComponent(identifier)}?${qs.toString()}`
    );
  },
  getCachedPlayerNames: () =>
    apiFetch<{ usernames: string[] }>("/api/players/cached-names"),

  recommendDefense: async (payload: {
    opponent: string;
    opponent_profile_id?: string;
    player?: string;
    player_profile_id?: string;
    categories: string[];
    difficulties?: (number | null)[];
    prior_weight?: number;
    refresh?: boolean;
  }) => {
    if (isExtensionAuthActive()) {
      const oppProfile = await fetchProfileViaExtension(
        payload.opponent,
        payload.opponent_profile_id,
        payload.refresh
      );
      const hasAnyDiff = Boolean(payload.difficulties?.some((d) => d !== null));
      let playerProfile: PlayerProfile | null = null;
      if (hasAnyDiff) {
        const extAuth = getExtensionAuth();
        const pId = payload.player || extAuth?.username || extAuth?.profile_id || "";
        if (pId) {
          playerProfile = await fetchProfileViaExtension(
            pId,
            payload.player_profile_id || (payload.player ? undefined : extAuth?.profile_id || undefined),
            payload.refresh
          );
        }
      }
      const manualRes = await apiFetch<ManualDefenseRecommendResponse>(
        "/api/defense/recommend-manual",
        {
          method: "POST",
          body: JSON.stringify({
            categories: payload.categories,
            opponent_metrics: oppProfile.category_metrics,
            player_metrics: playerProfile?.category_metrics,
            difficulties: payload.difficulties,
            prior_weight: payload.prior_weight,
          }),
        }
      );
      return {
        opponent: oppProfile.formatted_username,
        opponent_profile_id: oppProfile.profile_id,
        player: playerProfile?.formatted_username ?? null,
        mode: manualRes.mode,
        expected_opponent_points: manualRes.expected_opponent_points,
        recommendations: manualRes.recommendations,
      } satisfies DefenseRecommendResponse;
    }
    return apiFetch<DefenseRecommendResponse>("/api/defense/recommend", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  parseStatsScreenshot: (payload: { image_base64?: string; raw_text?: string }) =>
    apiFetch<ParseStatsScreenshotResponse>("/api/defense/parse-stats-screenshot", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  recommendDefenseManual: (payload: {
    categories: string[];
    opponent_metrics: Record<string, CategoryMetric>;
    player_metrics?: Record<string, CategoryMetric>;
    difficulties?: (number | null)[];
    prior_weight?: number;
  }) =>
    apiFetch<ManualDefenseRecommendResponse>("/api/defense/recommend-manual", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getHun: async (player1: string, player2: string, player2Id?: string, refresh = false) => {
    if (isExtensionAuthActive()) {
      const [p1, p2] = await Promise.all([
        fetchProfileViaExtension(player1, undefined, refresh),
        fetchProfileViaExtension(player2, player2Id, refresh),
      ]);
      return apiFetch<{
        player1: string;
        player2: string;
        score: number;
        shared_questions: number;
        matching_outcomes: number;
      }>("/api/extension/hun", {
        method: "POST",
        body: JSON.stringify({
          player1: p1.formatted_username,
          player2: p2.formatted_username,
          qhist_1: p1.question_history,
          qhist_2: p2.question_history,
        }),
      });
    }
    const qs = new URLSearchParams({ player1, player2, refresh: String(refresh) });
    if (player2Id) qs.set("player2_id", player2Id);
    return apiFetch<{
      player1: string;
      player2: string;
      score: number;
      shared_questions: number;
      matching_outcomes: number;
    }>(`/api/defense/hun?${qs.toString()}`);
  },
  getSimilarity: async (
    player1: string,
    player2: string,
    player2Id?: string,
    refresh = false
  ) => {
    if (isExtensionAuthActive()) {
      const [p1, p2] = await Promise.all([
        fetchProfileViaExtension(player1, undefined, refresh),
        fetchProfileViaExtension(player2, player2Id, refresh),
      ]);
      return apiFetch<{
        player1: string;
        player2: string;
        series: RadarPoint[];
      }>("/api/extension/similarity", {
        method: "POST",
        body: JSON.stringify({
          player1: p1.formatted_username,
          player2: p2.formatted_username,
          metrics_1: p1.category_metrics,
          metrics_2: p2.category_metrics,
        }),
      });
    }
    const qs = new URLSearchParams({ player1, player2, refresh: String(refresh) });
    if (player2Id) qs.set("player2_id", player2Id);
    return apiFetch<{
      player1: string;
      player2: string;
      series: RadarPoint[];
    }>(`/api/defense/similarity?${qs.toString()}`);
  },
  getTodaysQuestions: async (showAnswers: boolean, season?: number, day?: number) => {
    if (isExtensionAuthActive()) {
      let resolvedSeason = season;
      let resolvedDay = day;
      if (resolvedSeason === undefined || resolvedDay === undefined) {
        const latest = await api.getLatestSeason();
        resolvedSeason = resolvedSeason ?? latest.latest_season;
        resolvedDay = resolvedDay ?? latest.current_day + 1;
      }
      const html = await extFetchText(
        `${LL_BASE}/match.php?${resolvedSeason}&${resolvedDay}`
      );
      return apiFetch<TodaysQuestionsResponse>(
        "/api/extension/parse-todays-questions",
        {
          method: "POST",
          body: JSON.stringify({
            html,
            season: resolvedSeason,
            day: resolvedDay,
            show_answers: showAnswers,
          }),
        }
      );
    }
    const qs = new URLSearchParams({ show_answers: String(showAnswers) });
    if (season !== undefined) qs.set("season", String(season));
    if (day !== undefined) qs.set("day", String(day));
    return apiFetch<TodaysQuestionsResponse>(
      `/api/defense/todays-questions?${qs.toString()}`
    );
  },

  getLatestSeason: async () => {
    if (isExtensionAuthActive()) {
      const html = await extFetchText(`${LL_BASE}/allrundles.php`);
      return apiFetch<{ latest_season: number; current_day: number }>(
        "/api/extension/parse-season-day",
        {
          method: "POST",
          body: JSON.stringify({ html }),
        }
      );
    }
    return apiFetch<{ latest_season: number; current_day: number }>(
      "/api/luck/latest-season"
    );
  },
  analyzeLuck: async (payload: {
    season?: number;
    usernames: string[];
    extra_fields: string[];
    rundle_flag: boolean;
    use_sos: boolean;
    divide_pairs?: [string, string][];
    refresh?: boolean;
  }) => {
    if (isExtensionAuthActive()) {
      const allrundlesUrl =
        payload.season !== undefined
          ? `${LL_BASE}/allrundles.php?${payload.season}`
          : `${LL_BASE}/allrundles.php`;
      const allrundlesHtml = await extFetchText(allrundlesUrl);
      const seasonInfo = await apiFetch<{ latest_season: number; current_day: number }>(
        "/api/extension/parse-season-day",
        {
          method: "POST",
          body: JSON.stringify({ html: allrundlesHtml }),
        }
      );
      const resolvedSeason = payload.season ?? seasonInfo.latest_season;
      const csvText = await extFetchText(`${LL_BASE}/lgwide.php?${resolvedSeason}`);
      return apiFetch<LuckAnalysisResponse>("/api/extension/analyze-luck", {
        method: "POST",
        body: JSON.stringify({
          csv_text: csvText,
          season: resolvedSeason,
          matchday: seasonInfo.current_day,
          usernames: payload.usernames,
          extra_fields: payload.extra_fields,
          rundle_flag: payload.rundle_flag,
          use_sos: payload.use_sos,
          divide_pairs: payload.divide_pairs ?? [],
        }),
      });
    }
    return apiFetch<LuckAnalysisResponse>("/api/luck/analyze", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
};

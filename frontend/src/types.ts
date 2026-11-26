export interface AppMeta {
  mode: "web" | "desktop";
  version: string;
  update: {
    current_version: string;
    latest_version: string;
    update_available: boolean;
    release_url: string;
  };
  question_count: number;
  latest_season: number;
  current_day: number;
  sync_status: {
    running: boolean;
    phase: string;
    latest_season: number | null;
    current_day: number | null;
    total_missing_days: number;
    completed_days: number;
    last_synced_at: string | null;
    last_error: string | null;
  };
  access_gate_required: boolean;
  access_gate_unlocked: boolean;
  has_legacy_login_file: boolean;
  categories: string[];
  luck_fields: string[];
  stats_definition: Record<string, string>;
  modkos_url: string;
}

export interface AuthMe {
  authenticated: boolean;
  username: string | null;
  formatted_username: string | null;
  profile_id: string | null;
  desktop_keychain_available: boolean;
  has_saved_keychain_session: boolean;
  has_legacy_login_file: boolean;
}

export interface QuestionItem {
  qcode: string;
  season: number;
  day: number;
  q_num: number;
  question_num: string;
  question: string;
  answer: string;
  category: string;
  percent: number;
  defense: string;
  date: string;
  url: string;
  clickable_link: string;
  rundles: Record<"A" | "B" | "C" | "D" | "E" | "R", string>;
}

export interface QuestionsResponse {
  items: QuestionItem[];
  total: number;
  categories: string[];
  seasons: number[];
}

export interface GradeResponse {
  correct: boolean;
  score: number;
  matched_variant: string | null;
  variants: string[];
}

export interface OneDayCatalogItem {
  slug: string;
  title: string;
  url: string;
  date: string;
}

export interface OneDayQuestion {
  question_num: string;
  question: string;
  answer: string;
  percent: number;
}

export interface OneDayDetail {
  slug: string;
  title: string;
  date: string;
  url: string;
  blurb: string;
  difficulty_rating: string;
  overall_average: number;
  p90: number | null;
  p50: number | null;
  p10: number | null;
  percentiles: Record<string, number>;
  number_of_players: number;
  questions: OneDayQuestion[];
}

export interface MiniLeagueCatalogItem {
  slug: string;
  title: string;
  url: string;
  date: string;
  num_players: string;
}

export interface MiniLeagueQuestion {
  index: number;
  day: number;
  label: string;
  question: string;
  answer: string;
  percent: number;
}

export interface MiniLeagueDetail {
  slug: string;
  title: string;
  date: string;
  url: string;
  num_players: string;
  overall_correct: number;
  total_questions: number;
  match_days: {
    day: number;
    label: string;
    questions: MiniLeagueQuestion[];
  }[];
}

export interface MockDayQuestion extends QuestionItem {
  index: number;
  assigned_point: number;
}

export interface MockDayPayload {
  uuid: string;
  code: string;
  date: string;
  seed: number | null;
  threshold: number;
  questions: MockDayQuestion[];
}

export interface CategoryMetric {
  correct: number;
  total: number;
  percent: number;
}

export interface PlayerQuestionHistoryItem {
  question_category: string;
  correct: boolean;
  question: string;
  url: string;
}

export interface PlayerProfile {
  profile_id: string;
  username: string;
  formatted_username: string;
  link: string;
  opponents: Record<string, string>;
  category_metrics: Record<string, CategoryMetric>;
  question_history: Record<string, PlayerQuestionHistoryItem>;
  stats: {
    total: Record<string, string>;
    current_season: Record<string, string>;
  };
  past_seasons: Record<string, unknown>;
}

export interface DefenseRecommendation {
  slot: number;
  category: string;
  opponent_percent: number;
  recommended_points: number;
  difficulty: number | null;
  estimated_opponent_pct: number;
  estimated_ground_truth_pct: number | null;
}

export interface DefenseRecommendResponse {
  opponent: string;
  opponent_profile_id: string;
  player: string | null;
  mode: "irt" | "category_only";
  expected_opponent_points: number;
  recommendations: DefenseRecommendation[];
}

export interface ParseStatsScreenshotResponse {
  category_metrics: Record<string, CategoryMetric>;
  matched_count: number;
  missing_categories: string[];
  raw_text: string;
}

export interface ManualDefenseRecommendResponse {
  mode: "irt" | "category_only";
  expected_opponent_points: number;
  recommendations: DefenseRecommendation[];
}

export interface RadarPoint {
  category: string;
  player1_pct: number;
  player2_pct: number;
}

export interface TodaysQuestionsResponse {
  status: "ok" | "no_active_match" | "not_yet_active";
  season: number;
  day: number;
  message: string;
  questions: {
    id: number;
    question: string;
    submitted_answer: string;
    correct_answer: string;
    points_assigned: string;
  }[];
}

export interface LuckAnalysisResponse {
  season: number;
  matchday: number;
  columns: string[];
  rows: Record<string, string | number | null>[];
  matched_usernames: string[];
  missing_usernames: string[];
  formula: string;
  r_squared: number;
  total_players: number;
}

export interface PracticeAnswerRecord {
  id: number | string;
  qcode: string;
  submitted_answer: string;
  correct: boolean;
  override: boolean;
  answered_at: string;
}

export interface PersonalDataExport {
  version: number;
  exported_at: string;
  practice_answers: PracticeAnswerRecord[];
  favorites: string[];
  oneday_attempts: {
    slug: string;
    title: string;
    score: number;
    percentile: string;
    completed_at: string;
    payload: Record<string, unknown>;
  }[];
  mock_days: {
    uuid: string;
    code: string;
    seed: number | null;
    threshold: number;
    created_at: string;
    payload: Record<string, unknown>;
  }[];
}

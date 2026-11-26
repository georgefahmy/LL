from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class GateVerifyRequest(BaseModel):
    code: str


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)
    remember_me: bool = False


class CookieLoginRequest(BaseModel):
    cookie: str = Field(..., min_length=1)
    remember_me: bool = False


class GradeRequest(BaseModel):
    submitted_answer: str
    correct_answer: str


class OneDayAnswerItem(BaseModel):
    question_num: str
    submitted_answer: str
    money_question: bool = False
    override: bool | None = None


class OneDayGradeRequest(BaseModel):
    slug: str
    answers: list[OneDayAnswerItem]


class MockDayRequest(BaseModel):
    seed: int | None = None
    threshold: int = Field(default=0, ge=0, le=95)


class DefenseRecommendRequest(BaseModel):
    opponent: str
    opponent_profile_id: str | None = None
    player: str | None = None
    player_profile_id: str | None = None
    categories: list[str] = Field(..., min_length=6, max_length=6)
    difficulties: list[int | None] | None = Field(default=None, min_length=6, max_length=6)
    prior_weight: float = Field(default=8.0, ge=0.0, le=100.0)
    refresh: bool = False


class CategoryMetricInput(BaseModel):
    correct: int = Field(default=0, ge=0)
    total: int = Field(default=0, ge=0)
    percent: float = Field(default=0.0, ge=0.0, le=1.0)


class ParseStatsScreenshotRequest(BaseModel):
    image_base64: str | None = None
    raw_text: str | None = None


class ManualDefenseRecommendRequest(BaseModel):
    categories: list[str] = Field(..., min_length=6, max_length=6)
    opponent_metrics: dict[str, CategoryMetricInput]
    player_metrics: dict[str, CategoryMetricInput] | None = None
    difficulties: list[int | None] | None = Field(default=None, min_length=6, max_length=6)
    prior_weight: float = Field(default=8.0, ge=0.0, le=100.0)


class LuckAnalyzeRequest(BaseModel):
    season: int | None = Field(default=None, ge=60, le=500)
    matchday: int | None = Field(default=None, ge=0, le=25)
    usernames: list[str] = Field(default_factory=list)
    extra_fields: list[str] = Field(default_factory=list)
    rundle_flag: bool = False
    use_sos: bool = False
    divide_pairs: list[tuple[str, str]] = Field(default_factory=list)
    refresh: bool = False


class PracticeAnswerCreate(BaseModel):
    qcode: str
    submitted_answer: str
    correct: bool
    override: bool = False


class PracticeAnswerOverride(BaseModel):
    correct: bool
    override: bool = True


class FavoritesPut(BaseModel):
    usernames: list[str]


class OneDayAttemptSave(BaseModel):
    slug: str
    title: str
    score: int
    percentile: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)


class MockDaySave(BaseModel):
    uuid: str
    code: str
    seed: int | None = None
    threshold: int = 0
    payload: dict[str, Any] = Field(default_factory=dict)


class ExtensionParseProfileRequest(BaseModel):
    latest_html: str = Field(..., min_length=1)
    qhist_html: str = ""
    stats_html: str = ""
    past_html: str = ""


class ExtensionParseTodaysQuestionsRequest(BaseModel):
    html: str = Field(..., min_length=1)
    season: int
    day: int
    show_answers: bool = False


class ExtensionParseSeasonDayRequest(BaseModel):
    html: str = Field(..., min_length=1)


class ExtensionHunRequest(BaseModel):
    player1: str
    player2: str
    qhist_1: dict[str, dict[str, Any]]
    qhist_2: dict[str, dict[str, Any]]


class ExtensionSimilarityRequest(BaseModel):
    player1: str
    player2: str
    metrics_1: dict[str, dict[str, Any]]
    metrics_2: dict[str, dict[str, Any]]


class ExtensionAnalyzeLuckRequest(BaseModel):
    csv_text: str = Field(..., min_length=1)
    season: int
    matchday: int = 25
    usernames: list[str] = Field(default_factory=list)
    extra_fields: list[str] = Field(default_factory=list)
    rundle_flag: bool = False
    use_sos: bool = False
    divide_pairs: list[tuple[str, str]] = Field(default_factory=list)


class ExtensionSyncPlanRequest(BaseModel):
    allrundles_html: str = Field(..., min_length=1)
    max_days: int = Field(default=25, ge=1, le=50)


class ExtensionIngestMatchdayRequest(BaseModel):
    season: int = Field(..., ge=60, le=500)
    day: int = Field(..., ge=1, le=25)
    html: str = Field(..., min_length=1)

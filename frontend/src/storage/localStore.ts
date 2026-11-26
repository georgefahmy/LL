import { openDB, type IDBPDatabase } from "idb";

import { apiFetch } from "../api/client";
import type { PersonalDataExport, PracticeAnswerRecord } from "../types";

const DB_NAME = "learnedleague-local-v9";
const DB_VERSION = 1;
const LS_FALLBACK_KEY = "ll-personal-data-fallback";

export interface LocalStore {
  recordPracticeAnswer(input: {
    qcode: string;
    submitted_answer: string;
    correct: boolean;
    override?: boolean;
  }): Promise<number | string>;
  overridePracticeAnswer(
    id: number | string,
    correct: boolean,
    override?: boolean
  ): Promise<void>;
  listPracticeAnswers(qcode?: string): Promise<PracticeAnswerRecord[]>;
  getFavorites(): Promise<string[]>;
  setFavorites(usernames: string[]): Promise<string[]>;
  saveOneDayAttempt(input: {
    slug: string;
    title: string;
    score: number;
    percentile: string;
    payload: Record<string, unknown>;
  }): Promise<void>;
  listOneDayAttempts(): Promise<PersonalDataExport["oneday_attempts"]>;
  saveMockDay(input: {
    uuid: string;
    code: string;
    seed: number | null;
    threshold: number;
    payload: Record<string, unknown>;
  }): Promise<void>;
  exportAll(): Promise<PersonalDataExport>;
  importAll(data: PersonalDataExport): Promise<void>;
}

class DesktopLocalStore implements LocalStore {
  async recordPracticeAnswer(input: {
    qcode: string;
    submitted_answer: string;
    correct: boolean;
    override?: boolean;
  }): Promise<number> {
    const res = await apiFetch<{ id: number }>("/api/local-store/practice-answers", {
      method: "POST",
      body: JSON.stringify(input),
    });
    return res.id;
  }

  async overridePracticeAnswer(
    id: number | string,
    correct: boolean,
    override = true
  ): Promise<void> {
    await apiFetch(`/api/local-store/practice-answers/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ correct, override }),
    });
  }

  async listPracticeAnswers(qcode?: string): Promise<PracticeAnswerRecord[]> {
    const qs = qcode ? `?qcode=${encodeURIComponent(qcode)}` : "";
    const res = await apiFetch<{ items: PracticeAnswerRecord[] }>(
      `/api/local-store/practice-answers${qs}`
    );
    return res.items;
  }

  async getFavorites(): Promise<string[]> {
    const res = await apiFetch<{ usernames: string[] }>("/api/local-store/favorites");
    return res.usernames;
  }

  async setFavorites(usernames: string[]): Promise<string[]> {
    const res = await apiFetch<{ usernames: string[] }>("/api/local-store/favorites", {
      method: "PUT",
      body: JSON.stringify({ usernames }),
    });
    return res.usernames;
  }

  async saveOneDayAttempt(input: {
    slug: string;
    title: string;
    score: number;
    percentile: string;
    payload: Record<string, unknown>;
  }): Promise<void> {
    await apiFetch("/api/local-store/onedays", {
      method: "POST",
      body: JSON.stringify(input),
    });
  }

  async listOneDayAttempts(): Promise<PersonalDataExport["oneday_attempts"]> {
    const res = await apiFetch<{ items: PersonalDataExport["oneday_attempts"] }>(
      "/api/local-store/onedays"
    );
    return res.items;
  }

  async saveMockDay(input: {
    uuid: string;
    code: string;
    seed: number | null;
    threshold: number;
    payload: Record<string, unknown>;
  }): Promise<void> {
    await apiFetch("/api/local-store/mock-days", {
      method: "POST",
      body: JSON.stringify(input),
    });
  }

  async exportAll(): Promise<PersonalDataExport> {
    return apiFetch<PersonalDataExport>("/api/local-store/export");
  }

  async importAll(data: PersonalDataExport): Promise<void> {
    await apiFetch("/api/local-store/import", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }
}

class BrowserLocalStore implements LocalStore {
  private dbPromise: Promise<IDBPDatabase> | null = null;

  private async getDb(): Promise<IDBPDatabase | null> {
    if (typeof indexedDB === "undefined") return null;
    try {
      if (!this.dbPromise) {
        this.dbPromise = openDB(DB_NAME, DB_VERSION, {
          upgrade(db) {
            if (!db.objectStoreNames.contains("practice_answers")) {
              const store = db.createObjectStore("practice_answers", {
                keyPath: "id",
                autoIncrement: true,
              });
              store.createIndex("by_qcode", "qcode");
            }
            if (!db.objectStoreNames.contains("kv")) {
              db.createObjectStore("kv");
            }
            if (!db.objectStoreNames.contains("onedays")) {
              db.createObjectStore("onedays", { keyPath: "slug" });
            }
            if (!db.objectStoreNames.contains("mock_days")) {
              db.createObjectStore("mock_days", { keyPath: "uuid" });
            }
          },
        });
      }
      return await this.dbPromise;
    } catch {
      return null;
    }
  }

  private readFallback(): PersonalDataExport {
    try {
      const raw = localStorage.getItem(LS_FALLBACK_KEY);
      if (raw) return JSON.parse(raw) as PersonalDataExport;
    } catch {
      // Ignore storage errors
    }
    return {
      version: 1,
      exported_at: new Date().toISOString(),
      practice_answers: [],
      favorites: [],
      oneday_attempts: [],
      mock_days: [],
    };
  }

  private writeFallback(data: PersonalDataExport): void {
    try {
      localStorage.setItem(LS_FALLBACK_KEY, JSON.stringify(data));
    } catch {
      // Ignore storage errors
    }
  }

  async recordPracticeAnswer(input: {
    qcode: string;
    submitted_answer: string;
    correct: boolean;
    override?: boolean;
  }): Promise<number> {
    const rec = {
      qcode: input.qcode,
      submitted_answer: input.submitted_answer,
      correct: input.correct,
      override: Boolean(input.override),
      answered_at: new Date().toISOString(),
    };
    const db = await this.getDb();
    if (db) {
      return Number(await db.add("practice_answers", rec));
    }
    const fb = this.readFallback();
    const id = Date.now();
    fb.practice_answers.unshift({ id, ...rec });
    this.writeFallback(fb);
    return id;
  }

  async overridePracticeAnswer(
    id: number | string,
    correct: boolean,
    override = true
  ): Promise<void> {
    const db = await this.getDb();
    if (db) {
      const numId = Number(id);
      const existing = (await db.get("practice_answers", numId)) as
        | PracticeAnswerRecord
        | undefined;
      if (existing) {
        await db.put("practice_answers", { ...existing, correct, override });
      }
      return;
    }
    const fb = this.readFallback();
    const row = fb.practice_answers.find((r) => r.id === id);
    if (row) {
      row.correct = correct;
      row.override = override;
      this.writeFallback(fb);
    }
  }

  async listPracticeAnswers(qcode?: string): Promise<PracticeAnswerRecord[]> {
    const db = await this.getDb();
    if (db) {
      const rows = qcode
        ? ((await db.getAllFromIndex(
            "practice_answers",
            "by_qcode",
            qcode
          )) as PracticeAnswerRecord[])
        : ((await db.getAll("practice_answers")) as PracticeAnswerRecord[]);
      return rows.sort((a, b) => Number(b.id) - Number(a.id));
    }
    const fb = this.readFallback();
    return qcode
      ? fb.practice_answers.filter((r) => r.qcode === qcode)
      : fb.practice_answers;
  }

  async getFavorites(): Promise<string[]> {
    const db = await this.getDb();
    if (db) {
      const favs = (await db.get("kv", "favorites")) as string[] | undefined;
      return favs ?? [];
    }
    return this.readFallback().favorites;
  }

  async setFavorites(usernames: string[]): Promise<string[]> {
    const cleaned = Array.from(
      new Set(usernames.map((u) => u.trim()).filter(Boolean))
    ).sort((a, b) => a.toLowerCase().localeCompare(b.toLowerCase()));
    const db = await this.getDb();
    if (db) {
      await db.put("kv", cleaned, "favorites");
      return cleaned;
    }
    const fb = this.readFallback();
    fb.favorites = cleaned;
    this.writeFallback(fb);
    return cleaned;
  }

  async saveOneDayAttempt(input: {
    slug: string;
    title: string;
    score: number;
    percentile: string;
    payload: Record<string, unknown>;
  }): Promise<void> {
    const rec = { ...input, completed_at: new Date().toISOString() };
    const db = await this.getDb();
    if (db) {
      await db.put("onedays", rec);
      return;
    }
    const fb = this.readFallback();
    fb.oneday_attempts = [
      rec,
      ...fb.oneday_attempts.filter((x) => x.slug !== input.slug),
    ];
    this.writeFallback(fb);
  }

  async listOneDayAttempts(): Promise<PersonalDataExport["oneday_attempts"]> {
    const db = await this.getDb();
    if (db) {
      return (await db.getAll("onedays")) as PersonalDataExport["oneday_attempts"];
    }
    return this.readFallback().oneday_attempts;
  }

  async saveMockDay(input: {
    uuid: string;
    code: string;
    seed: number | null;
    threshold: number;
    payload: Record<string, unknown>;
  }): Promise<void> {
    const rec = { ...input, created_at: new Date().toISOString() };
    const db = await this.getDb();
    if (db) {
      await db.put("mock_days", rec);
      return;
    }
    const fb = this.readFallback();
    fb.mock_days = [rec, ...fb.mock_days.filter((x) => x.uuid !== input.uuid)];
    this.writeFallback(fb);
  }

  async exportAll(): Promise<PersonalDataExport> {
    const db = await this.getDb();
    if (!db) return this.readFallback();
    const [practice_answers, favorites, oneday_attempts, mock_days] =
      await Promise.all([
        this.listPracticeAnswers(),
        this.getFavorites(),
        this.listOneDayAttempts(),
        db.getAll("mock_days") as Promise<PersonalDataExport["mock_days"]>,
      ]);
    return {
      version: 1,
      exported_at: new Date().toISOString(),
      practice_answers,
      favorites,
      oneday_attempts,
      mock_days,
    };
  }

  async importAll(data: PersonalDataExport): Promise<void> {
    const db = await this.getDb();
    if (!db) {
      const fb = this.readFallback();
      const mergedFavs = Array.from(
        new Set([...(fb.favorites || []), ...(data.favorites || [])])
      );
      this.writeFallback({
        ...fb,
        favorites: mergedFavs,
        practice_answers: [...(data.practice_answers || []), ...fb.practice_answers],
        oneday_attempts: [...(data.oneday_attempts || []), ...fb.oneday_attempts],
        mock_days: [...(data.mock_days || []), ...fb.mock_days],
      });
      return;
    }

    if (Array.isArray(data.favorites)) {
      const existing = await this.getFavorites();
      await this.setFavorites([...existing, ...data.favorites]);
    }
    if (Array.isArray(data.practice_answers)) {
      for (const ans of data.practice_answers) {
        await db.add("practice_answers", {
          qcode: ans.qcode,
          submitted_answer: ans.submitted_answer,
          correct: ans.correct,
          override: ans.override,
          answered_at: ans.answered_at || new Date().toISOString(),
        });
      }
    }
    if (Array.isArray(data.oneday_attempts)) {
      for (const od of data.oneday_attempts) {
        await db.put("onedays", od);
      }
    }
    if (Array.isArray(data.mock_days)) {
      for (const md of data.mock_days) {
        await db.put("mock_days", md);
      }
    }
  }
}

export function createLocalStore(mode: "web" | "desktop"): LocalStore {
  return mode === "desktop" ? new DesktopLocalStore() : new BrowserLocalStore();
}

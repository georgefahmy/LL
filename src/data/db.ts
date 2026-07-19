import Dexie, { type Table } from 'dexie';
import questionsJson from './questions.json';

export interface Question {
  id: string; // e.g. "S97D05Q2"
  question: string;
  answer: string;
  season: number;
  date: string;
  category: string;
  percent: string;
  question_num: string;
  defense: string;
  url: string;
  clickable_link: string;
  A: string;
  B: string;
  C: string;
  D: string;
  E: string;
  R: string;
}

export interface UserAnswer {
  id?: number;
  question_id: string;
  submitted_answer: string;
  date: string;
  correct: number; // 0 or 1
  override: number; // 0 or 1
}

export interface Setting {
  key: string;
  value: string;
}

export class LearnedLeagueDatabase extends Dexie {
  questions!: Table<Question, string>;
  user_answers!: Table<UserAnswer, number>;
  settings!: Table<Setting, string>;

  constructor() {
    super('LearnedLeagueDatabase');
    this.version(1).stores({
      questions: 'id, season, category, percent',
      user_answers: '++id, question_id, date',
      settings: 'key'
    });
  }
}

export const dbInstance = new LearnedLeagueDatabase();

export async function initializeDatabaseIfEmpty() {
  try {
    console.log("[DB] Checking question count...");
    const count = await dbInstance.questions.count();
    console.log(`[DB] Current question count in IndexedDB: ${count}`);
    if (count === 0) {
      const isArr = Array.isArray(questionsJson);
      console.log(`[DB] Database is empty. questionsJson type: ${typeof questionsJson}, isArray: ${isArr}`);
      if (isArr) {
        console.log(`[DB] Importing ${questionsJson.length} questions...`);
        await dbInstance.questions.bulkPut(questionsJson as Question[]);
        const newCount = await dbInstance.questions.count();
        console.log(`[DB] Successfully imported. New count: ${newCount}`);
      } else {
        console.error("[DB] Error: questions.json is not an array!");
      }
    }
  } catch (err) {
    console.error("[DB] Error in initializeDatabaseIfEmpty:", err);
  }
}

export async function loadAllQuestions(): Promise<Question[]> {
  await initializeDatabaseIfEmpty();
  return dbInstance.questions.toArray();
}

export async function getQuestionAnswersHistory(qId: string): Promise<UserAnswer[]> {
  return dbInstance.user_answers.where('question_id').equals(qId).toArray();
}

export async function saveUserAnswer(ans: UserAnswer): Promise<number> {
  return dbInstance.user_answers.add(ans);
}

export async function updateUserAnswer(id: number, correct: boolean) {
  return dbInstance.user_answers.update(id, {
    correct: correct ? 1 : 0,
    override: 1
  });
}

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
  const count = await dbInstance.questions.count();
  if (count === 0) {
    console.log("Database is empty, importing questions.json...");
    // Bulk add questions
    await dbInstance.questions.bulkAdd(questionsJson as Question[]);
    console.log(`Successfully imported ${questionsJson.length} questions into IndexedDB.`);
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

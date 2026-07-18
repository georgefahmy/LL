import sqlite3
import os
import json
from src.constants import BASE_USER_DATA_DIR, WD

DB_PATH = os.path.join(BASE_USER_DATA_DIR, "all_data.db")
JSON_PATH = os.path.join(BASE_USER_DATA_DIR, "all_data.json")
FALLBACK_JSON_PATH = os.path.join(WD, "resources", "all_data.json")

def get_db_connection():
    if not os.path.isdir(BASE_USER_DATA_DIR):
        os.makedirs(BASE_USER_DATA_DIR, exist_ok=True)
    return sqlite3.connect(DB_PATH)

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create questions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS questions (
            id TEXT PRIMARY KEY,
            question TEXT,
            answer TEXT,
            season INTEGER,
            date TEXT,
            category TEXT,
            percent TEXT,
            question_num TEXT,
            defense TEXT,
            url TEXT,
            clickable_link TEXT,
            rundle_a TEXT,
            rundle_b TEXT,
            rundle_c TEXT,
            rundle_d TEXT,
            rundle_e TEXT,
            rundle_r TEXT
        )
    """)
    
    # Create user_answers table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_answers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_id TEXT,
            submitted_answer TEXT,
            date TEXT,
            correct INTEGER,
            override INTEGER,
            FOREIGN KEY (question_id) REFERENCES questions(id)
        )
    """)
    
    conn.commit()
    
    # Check if we need to migrate from JSON
    cursor.execute("SELECT COUNT(*) FROM questions")
    count = cursor.fetchone()[0]
    if count == 0:
        migrate_json_to_sqlite(conn)
        
    conn.close()

def migrate_json_to_sqlite(conn):
    # Determine which JSON path to use
    json_to_load = None
    if os.path.isfile(JSON_PATH):
        json_to_load = JSON_PATH
    elif os.path.isfile(FALLBACK_JSON_PATH):
        json_to_load = FALLBACK_JSON_PATH
        
    if not json_to_load:
        return
        
    print(f"Migrating {json_to_load} to SQLite database...")
    try:
        with open(json_to_load, "r") as fp:
            data = json.load(fp)
    except Exception as e:
        print(f"Error loading JSON for migration: {e}")
        return

    cursor = conn.cursor()
    
    questions_to_insert = []
    answers_to_insert = []
    
    for key, val in data.items():
        # Ensure we have strings/scalars correct
        q_id = key
        # Handle _question vs question key
        question_text = val.get("_question") or val.get("question") or ""
        answer = val.get("answer") or ""
        season = int(val.get("season", 0))
        date = val.get("date") or ""
        category = val.get("category") or ""
        percent = val.get("percent") or ""
        question_num = val.get("question_num") or ""
        defense = val.get("defense") or ""
        url = val.get("url") or ""
        clickable_link = val.get("clickable_link") or ""
        
        rundle_a = val.get("A") or ""
        rundle_b = val.get("B") or ""
        rundle_c = val.get("C") or ""
        rundle_d = val.get("D") or ""
        rundle_e = val.get("E") or ""
        rundle_r = val.get("R") or ""
        
        questions_to_insert.append((
            q_id, question_text, answer, season, date, category, percent,
            question_num, defense, url, clickable_link,
            rundle_a, rundle_b, rundle_c, rundle_d, rundle_e, rundle_r
        ))
        
        # User answers
        user_ans_list = val.get("answers") or []
        for ans in user_ans_list:
            answers_to_insert.append((
                q_id,
                ans.get("answer", ""),
                ans.get("date", ""),
                1 if ans.get("correct") else 0,
                1 if ans.get("override") else 0
            ))
            
    if questions_to_insert:
        cursor.executemany("""
            INSERT OR REPLACE INTO questions (
                id, question, answer, season, date, category, percent,
                question_num, defense, url, clickable_link,
                rundle_a, rundle_b, rundle_c, rundle_d, rundle_e, rundle_r
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, questions_to_insert)
        
    if answers_to_insert:
        cursor.executemany("""
            INSERT INTO user_answers (
                question_id, submitted_answer, date, correct, override
            ) VALUES (?, ?, ?, ?, ?)
        """, answers_to_insert)
        
    conn.commit()
    print("Migration completed successfully.")

def load_all_data():
    """Loads all SQLite data into a nested dictionary structure identical to the original JSON format."""
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Load all questions
    cursor.execute("SELECT * FROM questions")
    questions_rows = cursor.fetchall()
    
    # Load all user answers grouped by question_id
    cursor.execute("SELECT question_id, submitted_answer, date, correct, override FROM user_answers")
    answers_rows = cursor.fetchall()
    
    # Map answers to their question ID
    answers_map = {}
    for q_id, sub_ans, date, correct, override in answers_rows:
        if q_id not in answers_map:
            answers_map[q_id] = []
        answers_map[q_id].append({
            "answer": sub_ans,
            "date": date,
            "correct": bool(correct),
            "override": bool(override)
        })
        
    # Construct final dictionary
    all_data = {}
    for row in questions_rows:
        q_id = row[0]
        all_data[q_id] = {
            "_question": row[1],
            "answer": row[2],
            "season": row[3],
            "date": row[4],
            "category": row[5],
            "percent": row[6],
            "question_num": row[7],
            "defense": row[8],
            "url": row[9],
            "clickable_link": row[10],
            "A": row[11],
            "B": row[12],
            "C": row[13],
            "D": row[14],
            "E": row[15],
            "R": row[16],
            "answers": answers_map.get(q_id, [])
        }
        
    conn.close()
    return all_data

def save_question(q_id, data):
    """Saves a single question to the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO questions (
            id, question, answer, season, date, category, percent,
            question_num, defense, url, clickable_link,
            rundle_a, rundle_b, rundle_c, rundle_d, rundle_e, rundle_r
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        q_id,
        data.get("_question") or data.get("question") or "",
        data.get("answer") or "",
        int(data.get("season", 0)),
        data.get("date") or "",
        data.get("category") or "",
        data.get("percent") or "",
        data.get("question_num") or "",
        data.get("defense") or "",
        data.get("url") or "",
        data.get("clickable_link") or "",
        data.get("A") or "",
        data.get("B") or "",
        data.get("C") or "",
        data.get("D") or "",
        data.get("E") or "",
        data.get("R") or ""
    ))
    conn.commit()
    conn.close()

def save_user_answer(q_id, answer_dict):
    """Inserts a new user answer for a question."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO user_answers (question_id, submitted_answer, date, correct, override)
        VALUES (?, ?, ?, ?, ?)
    """, (
        q_id,
        answer_dict.get("answer", ""),
        answer_dict.get("date", ""),
        1 if answer_dict.get("correct") else 0,
        1 if answer_dict.get("override") else 0
    ))
    conn.commit()
    conn.close()

def update_user_answers(q_id, answers_list):
    """Deletes all previous user answers for a question and writes the new list."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM user_answers WHERE question_id = ?", (q_id,))
    if answers_list:
        cursor.executemany("""
            INSERT INTO user_answers (question_id, submitted_answer, date, correct, override)
            VALUES (?, ?, ?, ?, ?)
        """, [
            (
                q_id,
                ans.get("answer", ""),
                ans.get("date", ""),
                1 if ans.get("correct") else 0,
                1 if ans.get("override") else 0
            ) for ans in answers_list
        ])
    conn.commit()
    conn.close()


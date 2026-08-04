# -*- coding: utf-8 -*-
"""
data/questions.csv(개념 문제) + data/cbt_questions.csv(실제 기출 CBT 문제)를 읽어
SQLite DB(data/quiz.db)를 만든다.
- questions 테이블: 문제 은행(매 실행마다 CSV 기준으로 재생성됨). source 컬럼으로 'concept'/'cbt' 구분
- attempts 테이블: 사용자별 풀이 기록(재실행해도 보존됨 = 오답노트/통계 데이터)
"""
import csv
import os
import sqlite3

BASE_DIR = os.path.dirname(__file__)
CSV_PATH = os.path.join(BASE_DIR, "data", "questions.csv")
CBT_CSV_PATH = os.path.join(BASE_DIR, "data", "cbt_questions.csv")
DB_PATH = os.path.join(BASE_DIR, "data", "quiz.db")


def _read_rows(path):
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return [
            (
                int(r["subject"]), r["tag"], r["question"],
                r["choice1"], r["choice2"], r["choice3"], r["choice4"],
                int(r["answer"]), r["explanation"], int(r["core_id"]), r["source"],
            )
            for r in reader
        ]


def main():
    if not os.path.exists(CSV_PATH):
        raise SystemExit(f"CSV가 없습니다: {CSV_PATH}  (먼저 generate_questions.py를 실행하세요)")
    if not os.path.exists(CBT_CSV_PATH):
        raise SystemExit(f"CSV가 없습니다: {CBT_CSV_PATH}  (먼저 generate_cbt_questions.py를 실행하세요)")

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    cur.execute("DROP TABLE IF EXISTS questions")
    cur.execute("""
        CREATE TABLE questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject INTEGER NOT NULL,
            tag TEXT NOT NULL,
            question TEXT NOT NULL,
            choice1 TEXT NOT NULL,
            choice2 TEXT NOT NULL,
            choice3 TEXT NOT NULL,
            choice4 TEXT NOT NULL,
            answer INTEGER NOT NULL,
            explanation TEXT NOT NULL,
            core_id INTEGER NOT NULL,
            source TEXT NOT NULL DEFAULT 'concept'
        )
    """)

    rows = _read_rows(CSV_PATH) + _read_rows(CBT_CSV_PATH)
    cur.executemany(
        "INSERT INTO questions (subject, tag, question, choice1, choice2, choice3, choice4, "
        "answer, explanation, core_id, source) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        rows,
    )

    # attempts 테이블은 재실행 시에도 유지(사용자 학습 기록 보존)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user TEXT NOT NULL,
            question_id INTEGER NOT NULL REFERENCES questions(id),
            chosen INTEGER NOT NULL,
            is_correct INTEGER NOT NULL,
            ts TEXT NOT NULL
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_attempts_user ON attempts(user)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_attempts_q ON attempts(question_id)")

    # 오답노트에서 사용자가 직접 '표시'해 둔 문제(정오답과 무관하게 북마크)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS flags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user TEXT NOT NULL,
            question_id INTEGER NOT NULL REFERENCES questions(id),
            ts TEXT NOT NULL,
            UNIQUE(user, question_id)
        )
    """)

    # 개념노트 OX 퀴즈에서 틀린 개념. 퀴즈 오답노트(attempts/flags)와는 별개로 관리한다.
    cur.execute("""
        CREATE TABLE IF NOT EXISTS ox_wrong (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user TEXT NOT NULL,
            concept_qid INTEGER NOT NULL REFERENCES questions(id),
            ts TEXT NOT NULL,
            UNIQUE(user, concept_qid)
        )
    """)

    # 개념노트 카드(단어 입력형/빈칸 채우기)에서 틀린 개념. 위 ox_wrong과 마찬가지로 별도 관리.
    cur.execute("""
        CREATE TABLE IF NOT EXISTS card_wrong (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user TEXT NOT NULL,
            concept_qid INTEGER NOT NULL REFERENCES questions(id),
            ts TEXT NOT NULL,
            UNIQUE(user, concept_qid)
        )
    """)

    con.commit()
    n_q = cur.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
    n_concept = cur.execute("SELECT COUNT(*) FROM questions WHERE source='concept'").fetchone()[0]
    n_cbt = cur.execute("SELECT COUNT(*) FROM questions WHERE source='cbt'").fetchone()[0]
    n_a = cur.execute("SELECT COUNT(*) FROM attempts").fetchone()[0]
    con.close()
    print(f"questions: {n_q}행 (concept {n_concept} / cbt {n_cbt}), attempts: 기존 기록 {n_a}행 보존 -> {DB_PATH}")


if __name__ == "__main__":
    main()

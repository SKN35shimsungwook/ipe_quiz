# -*- coding: utf-8 -*-
"""cbt_source_egi.py의 실제 기출 CBT 문제를 data/cbt_questions.csv로 저장한다."""
import csv
import os

from cbt_source_egi import CBT_QUESTIONS

OUT_DIR = os.path.join(os.path.dirname(__file__), "data")
OUT_PATH = os.path.join(OUT_DIR, "cbt_questions.csv")


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_PATH, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow([
            "id", "subject", "tag", "question",
            "choice1", "choice2", "choice3", "choice4",
            "answer", "explanation", "core_id", "source",
        ])
        for i, q in enumerate(CBT_QUESTIONS, start=1):
            # CBT 문항은 core_id 네임스페이스를 100000번대로 분리해 개념형 문항과 겹치지 않게 한다.
            writer.writerow([
                i, q["s"], q["t"], q["q"],
                q["c"][0], q["c"][1], q["c"][2], q["c"][3],
                q["a"] + 1,
                q["e"],
                100000 + i,
                "cbt",
            ])
    print(f"CBT questions: {len(CBT_QUESTIONS)} -> {OUT_PATH}")


if __name__ == "__main__":
    main()

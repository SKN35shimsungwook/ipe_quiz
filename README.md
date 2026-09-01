# 💻 정보처리기사 핵심요약 퀴즈

**정보처리기사 필기시험** 핵심 요약 문제를 풀면서 공부하는 Streamlit 퀴즈 앱이에요.
소프트웨어 설계·개발, 데이터베이스, 프로그래밍 언어, 정보시스템 구축 등 과목별 문제를
SQLite DB로 관리해요.

## 기능

- 과목별로 문제를 골라서 풀기
- 채점 결과와 함께 해설 확인
- CSV 데이터가 DB보다 최신이면 앱 실행 시 **자동으로 DB를 재생성**
  (Streamlit Cloud처럼 `git pull`만으로 코드가 갱신되는 배포 환경에서, 예전 DB가 새 CSV 내용을
  반영 못 하는 문제를 막기 위함)

## 기술 스택

| 기술 | 역할 |
|---|---|
| **Streamlit** | 퀴즈 화면 |
| **SQLite** | 문제은행 저장 (`db.py`, `build_db.py`) |
| **pandas / CSV** | `data/questions.csv`, `data/cbt_questions.csv`가 원본 문제 데이터 |

## 파일 구조

```
ipe_quiz/
├── app.py                    # Streamlit 앱 진입점
├── db.py                      # SQLite 연결 및 조회
├── build_db.py                 # CSV → SQLite DB 빌드
├── generate_questions.py       # 문제 데이터 생성/정리 스크립트
├── generate_cbt_questions.py    # CBT 문제은행 데이터 생성/정리 스크립트
├── cbt_source_egi.py            # CBT 원본 자료 처리
├── data/
│   ├── questions.csv              # 정리된 핵심요약 문제
│   └── cbt_questions.csv          # CBT(컴퓨터 기반 시험) 문제은행
└── requirements.txt
```

## 실행하기

```bash
pip install -r requirements.txt
streamlit run app.py
```

## 트러블슈팅

**Streamlit Cloud에 올리면 헬스체크마다 500 에러**

- 원인: `streamlit`(당시 1.61.0) 내장 gzip 미들웨어가 `GZipResponder`를 호출하는데, `starlette`가
  1.4.0으로 올라가면서 그 호출에 새로 필수가 된 `thread_minimum_size` 인자를 안 넘기고
  있어서, 배포된 앱이 뜨자마자 헬스체크 요청마다 크래시 났음.
- 해결: `requirements.txt`에 `starlette<1.4.0`으로 상한 버전 고정.

```diff
  streamlit>=1.57
+ starlette<1.4.0
```

---

🤖 이 저장소의 README는 Claude Code와 함께 작성했어요.

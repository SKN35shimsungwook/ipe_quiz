# 💻 정보처리기사 핵심요약 퀴즈

**🔗 바로 실행해 보기:** https://ipequiz-l5uazc8et59tsvbvsmdf8y.streamlit.app

**정보처리기사 필기**를 준비하면서, 핵심 요약을 문제로 풀면서 외우려고 만든 Streamlit 퀴즈 앱입니다.
소프트웨어 설계·개발, 데이터베이스, 프로그래밍 언어, 정보시스템 구축 등 과목별 문제를 SQLite DB로 관리합니다.

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

## 만들면서 겪은 문제

**Streamlit Cloud에 올리자 헬스체크마다 500 에러가 났습니다**

- 원인: `streamlit`(당시 1.61.0)의 gzip 미들웨어가 `GZipResponder`를 부를 때, `starlette` 1.4.0부터 필수가 된 `thread_minimum_size` 인자를 넘기지 않고 있었습니다. 그래서 앱이 뜨자마자 헬스체크 요청마다 죽었습니다.
- 해결: `requirements.txt`에서 `starlette<1.4.0`으로 버전을 묶었습니다. 내 코드가 아니라 라이브러리끼리의 버전 문제도 배포를 막을 수 있다는 걸 이때 배웠습니다.

```diff
  streamlit>=1.57
+ starlette<1.4.0
```

# -*- coding: utf-8 -*-
"""정보처리기사 필기 핵심요약 퀴즈 (Streamlit + SQLite)"""
import os
import random
import re

import streamlit as st

import build_db
import db

_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
_SOURCE_CSVS = [os.path.join(_DATA_DIR, "questions.csv"), os.path.join(_DATA_DIR, "cbt_questions.csv")]


def _db_is_stale():
    # 배포 환경(Streamlit Cloud)은 git pull만으로 코드를 갱신하는 경우가 있어,
    # 예전에 생성된 quiz.db가 새 CSV 내용을 반영하지 못한 채 그대로 남을 수 있다.
    # CSV가 DB보다 최신이면 재생성해서 코드 배포와 데이터가 항상 일치하도록 한다.
    if not os.path.exists(db.DB_PATH):
        return True
    db_mtime = os.path.getmtime(db.DB_PATH)
    return any(os.path.exists(p) and os.path.getmtime(p) > db_mtime for p in _SOURCE_CSVS)


if _db_is_stale():
    build_db.main()

st.set_page_config(page_title="정보처리기사 핵심요약 퀴즈", page_icon="💻", layout="centered")

SUBJECT_LABEL = {
    1: "1과목 소프트웨어 설계",
    2: "2과목 소프트웨어 개발",
    3: "3과목 데이터베이스 구축",
    4: "4과목 프로그래밍 언어 활용",
    5: "5과목 정보시스템 구축 관리",
}
SUBJECTS = list(SUBJECT_LABEL.keys())
SUBJECT_CHOICES = ["전체"] + [f"{s}과목" for s in SUBJECTS]
CIRCLE = ["①", "②", "③", "④"]

# 실제 정보처리기사 필기 시험 기준: 총 100문항(과목별 20문항 x 5과목), 문항당 1점,
# 과목별 40% 미만(8문항 미만)이면 과락, 전체 60점 이상이면 합격
EXAM_SUBJECT_COUNTS = {s: 20 for s in SUBJECTS}
EXAM_MIN_CORRECT = {s: 8 for s in SUBJECTS}
EXAM_TOTAL_QUESTIONS = 100
EXAM_TOTAL_PASS = 60
POINTS_PER_Q = 1

st.markdown(
    """
    <style>
    :root{
      --ink:#20242A; --ink-soft:#525A66; --paper:#F5F7FB; --card:#FFFFFF;
      --accent:#2454A6; --accent-soft:#E3EBF9; --line:#E1E6EF;
      --correct:#2F7D5D; --correct-soft:#E4F3EC;
      --wrong:#C23B33; --wrong-soft:#FBE7E5;
      --warn:#B9790E; --warn-soft:#FBF0DC;
    }
    .stButton > button{
      border-radius:14px !important;
      font-weight:700 !important;
      box-shadow:0 1px 2px rgba(32,36,42,.04), 0 4px 14px rgba(32,36,42,.05);
    }
    .stButton > button[kind="primary"]{
      background:var(--ink) !important;
      border-color:var(--ink) !important;
      border-radius:999px !important;
      padding:.65rem 1.6rem !important;
    }
    div[data-testid="stMetric"]{
      background:var(--card);border:1px solid var(--line);border-radius:14px;padding:10px 6px;
      box-shadow:0 1px 2px rgba(32,36,42,.04), 0 4px 14px rgba(32,36,42,.05);
    }
    .pill{display:inline-block;font-size:.75rem;font-weight:700;padding:3px 11px;
          border-radius:999px;background:var(--accent-soft);color:var(--accent);margin-right:6px;}
    .pill-tag{background:var(--paper);color:var(--ink-soft);border:1px solid var(--line);}
    .pill-src{background:#EAF1EC;color:#2F5D46;border:1px solid #D6E6DB;}
    .qbox{font-size:1.15rem;font-weight:700;line-height:1.5;margin:10px 0 18px;color:var(--ink);}
    .choice-row{padding:10px 14px;border:1px solid var(--line);border-radius:12px;margin-bottom:8px;background:var(--card);}
    .choice-correct{background:var(--correct-soft);border-color:var(--correct);color:var(--correct);font-weight:700;}
    .choice-wrong{background:var(--wrong-soft);border-color:var(--wrong);color:var(--wrong);font-weight:700;}
    .bar-track{height:8px;background:var(--paper);border-radius:99px;border:1px solid var(--line);overflow:hidden;}
    .bar-fill{height:100%;border-radius:99px;}
    .exam-pass{background:var(--correct-soft);border:1px solid var(--correct);color:#1F5C41;border-radius:16px;padding:20px;text-align:center;}
    .exam-fail{background:var(--wrong-soft);border:1px solid var(--wrong);color:#8C2A22;border-radius:16px;padding:20px;text-align:center;}
    .exam-pass .big, .exam-fail .big{font-size:1.6rem;font-weight:800;margin-bottom:4px;}
    .subj-row{display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid var(--line);font-size:.9rem;color:var(--ink);}
    .subj-badge{font-size:.72rem;font-weight:700;padding:2px 8px;border-radius:999px;}
    .subj-ok{background:var(--correct-soft);color:#1F5C41;}
    .subj-fail{background:var(--wrong-soft);color:#8C2A22;}
    .concept-summary{background:var(--accent-soft);border:1px solid var(--line);border-radius:10px;
      padding:8px 12px;font-size:.84rem;color:var(--ink-soft);margin:6px 0 14px;}
    .group-title{font-size:1rem;font-weight:800;color:var(--ink);margin:18px 0 4px;}
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def get_con():
    return db.get_connection()


@st.cache_data
def get_questions_by_id():
    con = get_con()
    return {r["id"]: dict(r) for r in db.get_all_questions(con)}


@st.cache_data
def get_core_groups():
    """subject -> {core_id: [qid, ...]} : 같은 개념(core_id)의 문항 변형들을 묶는다(개념형 문제 전용)."""
    groups = {s: {} for s in SUBJECTS}
    for qid, q in QUESTIONS.items():
        if q["source"] != "concept":
            continue
        groups[q["subject"]].setdefault(q["core_id"], []).append(qid)
    return groups


@st.cache_data
def get_tag_summary_map():
    """(subject, tag) -> 개념 요약 한 줄. 해당 개념의 대표 문제 해설을 재사용한다."""
    out = {}
    for qid, q in QUESTIONS.items():
        key = (q["subject"], q["tag"])
        if key not in out:
            out[key] = q["explanation"]
    return out


@st.cache_data
def get_concepts():
    """개념형 문제 은행에서 core_id(고유 개념)당 하나씩만 뽑은 대표 개념 목록.
    카드/노트/OX 퀴즈가 공통으로 사용하는 원천 데이터이다."""
    seen = {}
    for qid, q in QUESTIONS.items():
        if q["source"] != "concept":
            continue
        cid = q["core_id"]
        if cid not in seen:
            seen[cid] = q
    return sorted(seen.values(), key=lambda q: (q["subject"], q["tag"]))


QUESTIONS = get_questions_by_id()
ALL_IDS = list(QUESTIONS.keys())
CBT_IDS = [qid for qid, q in QUESTIONS.items() if q["source"] == "cbt"]


def pick_pool(subjects, limit=None):
    """subjects에 속한 개념형 문항을 core_id(개념) 기준으로 중복 없이 하나씩 무작위로 뽑는다.
    실행할 때마다 어떤 변형이 뽑힐지 달라지므로 매번 같은 문구로 고정되지 않는다."""
    groups = get_core_groups()
    pool = []
    for s in subjects:
        for variant_ids in groups[s].values():
            pool.append(random.choice(variant_ids))
    random.shuffle(pool)
    if limit:
        pool = pool[:limit]
    return pool


def _normalize_answer(s):
    return re.sub(r"\s+", "", s.strip().lower())


def _answer_matches(user_input, correct_text):
    """개념 카드 입력형 채점: 괄호 안 영문 약어/원어 표기도 정답으로 인정한다.
    예) "정규화(Normalization)" -> "정규화" 또는 "Normalization" 모두 정답 처리."""
    if not user_input or not user_input.strip():
        return False
    variants = {correct_text}
    m = re.match(r"^(.*?)\s*\(([^)]+)\)\s*$", correct_text)
    if m:
        variants.add(m.group(1).strip())
        variants.add(m.group(2).strip())
    u = _normalize_answer(user_input)
    return any(u == _normalize_answer(v) for v in variants if v)


def make_blank_sentence(explanation, answer_text):
    """해설 문장 안에서 정답 텍스트(또는 괄호 앞부분)를 찾아 빈칸으로 치환한다.
    찾지 못하면 None을 반환해 호출부가 단어 입력형으로 대체하도록 한다."""
    candidates = [answer_text]
    m = re.match(r"^(.*?)\s*\(([^)]+)\)\s*$", answer_text)
    if m:
        candidates = [answer_text, m.group(1).strip()]
    for cand in candidates:
        if cand and cand in explanation:
            return explanation.replace(cand, "〔　　　　〕", 1)
    return None


def cbt_selected_index(qid, prefix):
    """CBT 라디오 위젯(key=f"{prefix}_{qid}")에 저장된 '① 보기텍스트' 문자열을 0~3 인덱스로 변환한다."""
    sel = st.session_state.get(f"{prefix}_{qid}")
    if sel is None:
        return None
    q = QUESTIONS[qid]
    choices = [q["choice1"], q["choice2"], q["choice3"], q["choice4"]]
    return choices.index(sel[2:])


def pick_exam_pool():
    """실전 시험 모드: 과목별 공식 문항 수(각 20문항)만큼 개념 중복 없이 무작위로 뽑되,
    실제 시험지처럼 1->2->3->4->5과목 순서로 정렬해 반환한다(과목 내부만 무작위)."""
    groups = get_core_groups()
    ids = []
    for s, n in EXAM_SUBJECT_COUNTS.items():
        core_ids = list(groups[s].keys())
        random.shuffle(core_ids)
        subj_ids = [random.choice(groups[s][c]) for c in core_ids[:n]]
        ids.extend(subj_ids)
    return ids


def pick_cbt_pool(subjects, limit=None):
    """CBT 연습 모드: 선택한 과목의 기출문제 중 무작위로 뽑는다."""
    ids = [qid for qid in CBT_IDS if QUESTIONS[qid]["subject"] in subjects]
    random.shuffle(ids)
    if limit:
        ids = ids[:limit]
    return ids


def pick_cbt_exam_pool():
    """CBT 실전 모드: 실제 출제 기준(과목별 20문항)과 동일한 비율로 기출문제 풀에서
    무작위로 뽑되, 실제 시험지처럼 1->2->3->4->5과목 순서로 정렬해 반환한다
    (과목 내부만 무작위)."""
    ids = []
    for s, n in EXAM_SUBJECT_COUNTS.items():
        subj_ids = [qid for qid in CBT_IDS if QUESTIONS[qid]["subject"] == s]
        random.shuffle(subj_ids)
        ids.extend(subj_ids[:n])
    return ids


# ---------- session state ----------
ss = st.session_state
ss.setdefault("user", "")
ss.setdefault("nav", "퀴즈")
ss.setdefault("queue", None)
ss.setdefault("pos", 0)
ss.setdefault("answered", False)
ss.setdefault("chosen", None)
ss.setdefault("correct_count", 0)
ss.setdefault("wrong_ids", [])
ss.setdefault("quiz_title", "")
ss.setdefault("exam_mode", False)
ss.setdefault("exam_subject_correct", {})
ss.setdefault("cbt_view", None)
ss.setdefault("cbt_ids", [])
ss.setdefault("cbt_graded", False)
ss.setdefault("cbt_submitted", False)
ss.setdefault("cbt_checked", set())
ss.setdefault("cbt_recorded", set())
ss.setdefault("cbt_exam_subject_correct", {})
ss.setdefault("concept_view", "카드")
ss.setdefault("card_idx", 0)
ss.setdefault("card_flipped", False)
ss.setdefault("card_mode", "뒤집기")
ss.setdefault("ox_pool", None)
ss.setdefault("ox_pos", 0)
ss.setdefault("ox_correct", 0)
ss.setdefault("ox_answered", False)
ss.setdefault("ox_choice", None)
ss.setdefault("ox_wrong_view", False)
ss.setdefault("card_wrong_view", False)


def start_quiz(ids, title, exam_mode=False):
    ss.queue = ids
    ss.pos = 0
    ss.answered = False
    ss.chosen = None
    ss.correct_count = 0
    ss.wrong_ids = []
    ss.quiz_title = title
    ss["_pending_nav"] = "퀴즈"
    ss.exam_mode = exam_mode
    ss.exam_subject_correct = {s: 0 for s in SUBJECTS}


def quit_quiz():
    ss.queue = None
    ss.pos = 0
    ss.answered = False
    ss.chosen = None
    ss.exam_mode = False


def start_cbt(view, ids):
    ss.cbt_view = view
    ss.cbt_ids = ids
    ss.cbt_graded = False
    ss.cbt_submitted = False
    ss.cbt_checked = set()
    ss.cbt_recorded = set()
    ss.cbt_exam_subject_correct = {s: 0 for s in SUBJECTS}
    ss["_pending_nav"] = "CBT 모드"


def quit_cbt():
    ss.cbt_view = None
    ss.cbt_ids = []
    ss.cbt_graded = False
    ss.cbt_submitted = False
    ss.cbt_checked = set()
    ss.cbt_recorded = set()
    ss.cbt_exam_subject_correct = {}


# 다른 탭의 버튼(오답 복습, 집중 풀기 등)이 예약해 둔 탭 전환을 위젯이 그려지기 전에 반영한다.
# (위젯이 이미 그려진 뒤에는 key="nav" 상태를 코드에서 직접 바꿀 수 없다는 Streamlit 제약 때문)
if "_pending_nav" in ss:
    ss["nav"] = ss.pop("_pending_nav")

# ---------- sidebar ----------
with st.sidebar:
    st.header("정보처리기사 핵심요약 퀴즈")
    st.caption("정보처리기사 필기 자가 학습 · 4지선다")
    user_input = st.text_input("닉네임 (풀이 기록 저장용)", value=ss.user, placeholder="예: 홍길동")
    ss.user = user_input.strip()
    st.divider()
    nav_options = ["퀴즈", "CBT 모드", "개념노트", "오답노트", "자주 틀리는 개념"]
    # key="nav"로 위젯을 세션 상태(ss.nav)에 직접 바인딩한다.
    # (과거에는 index=로만 동기화했는데, 다른 탭의 버튼이 ss.nav를 바꿔도
    #  위젯 자체의 내부 상태가 우선시되어 탭 전환이 씹히는 버그가 있었다.)
    st.radio("메뉴", nav_options, key="nav")
    if ss.queue is not None:
        st.divider()
        if st.button("퀴즈 그만하기", width="stretch"):
            quit_quiz()
            st.rerun()
    if ss.cbt_view is not None:
        st.divider()
        if st.button("CBT 그만하기", width="stretch"):
            quit_cbt()
            st.rerun()

if not ss.user:
    st.info("사이드바에 닉네임을 입력하면 풀이 기록(오답노트·통계)이 저장됩니다.")
    ss.user = "guest"

con = get_con()

# ---------- top stats ----------
overall = db.get_overall_stats(con, ss.user)
need_ids, done_ids, _ = db.get_wrong_question_ids(con, ss.user)
flagged_ids = db.get_flagged_ids(con, ss.user)
c1, c2, c3 = st.columns(3)
c1.metric("누적 풀이", overall["seen"])
c2.metric("정답률", f"{overall['rate']}%")
c3.metric("복습 필요", len(need_ids))

st.divider()

# ============ 퀴즈 뷰 (개념 문제) ============
if ss.nav == "퀴즈":
    if ss.queue is None:
        st.subheader("퀴즈 시작하기")

        with st.container(border=True):
            st.markdown(f"**실전 시험 모드** — 실제 정보처리기사 필기 출제 기준(과목별 20문항, 총 {EXAM_TOTAL_QUESTIONS}문항)으로 합격/과락 여부까지 진단합니다.")
            if st.button(f"실전 시험 모드 시작 ({EXAM_TOTAL_QUESTIONS}문항)", type="primary", width="stretch"):
                start_quiz(pick_exam_pool(), "실전 시험 모드", exam_mode=True)
                st.rerun()

        st.markdown("#### 연습 모드")
        subject_choice = st.radio("과목 선택", SUBJECT_CHOICES, horizontal=True)
        count_choice = st.radio("문제 수", ["10문제", "20문제", "30문제", "전체"], horizontal=True, index=1)

        if need_ids:
            st.warning(f"복습이 필요한 오답이 {len(need_ids)}개 있어요.")
            if st.button("오답 복습으로 바로 시작"):
                start_quiz(need_ids, "오답 복습")
                st.rerun()

        if st.button("연습 퀴즈 시작", width="stretch"):
            if subject_choice == "전체":
                subjects = SUBJECTS
                title = "전체 문제"
            else:
                sub_num = int(subject_choice[0])
                subjects = [sub_num]
                title = SUBJECT_LABEL[sub_num]
            limit = None if count_choice == "전체" else int(count_choice.replace("문제", ""))
            start_quiz(pick_pool(subjects, limit), title)
            st.rerun()

    elif ss.pos < len(ss.queue):
        total = len(ss.queue)
        qid = ss.queue[ss.pos]
        q = QUESTIONS[qid]
        st.progress(ss.pos / total, text=f"{ss.quiz_title} · {ss.pos + 1} / {total}")
        st.markdown(
            f'<span class="pill">{SUBJECT_LABEL[q["subject"]]}</span>'
            f'<span class="pill pill-tag">{q["tag"]}</span>',
            unsafe_allow_html=True,
        )
        st.markdown(f'<div class="qbox">{q["question"]}</div>', unsafe_allow_html=True)

        choices = [q["choice1"], q["choice2"], q["choice3"], q["choice4"]]
        answer_idx = q["answer"] - 1

        if not ss.answered:
            for ci, choice_text in enumerate(choices):
                if st.button(f"{CIRCLE[ci]}  {choice_text}", key=f"choice_{qid}_{ci}", width="stretch"):
                    is_correct = ci == answer_idx
                    db.record_attempt(con, ss.user, int(qid), ci, is_correct)
                    ss.answered = True
                    ss.chosen = ci
                    if is_correct:
                        ss.correct_count += 1
                        if ss.exam_mode:
                            ss.exam_subject_correct[q["subject"]] = ss.exam_subject_correct.get(q["subject"], 0) + 1
                    else:
                        ss.wrong_ids.append(qid)
                    st.rerun()
        else:
            for ci, choice_text in enumerate(choices):
                cls = "choice-row"
                if ci == answer_idx:
                    cls += " choice-correct"
                elif ci == ss.chosen:
                    cls += " choice-wrong"
                st.markdown(f'<div class="{cls}">{CIRCLE[ci]}  {choice_text}</div>', unsafe_allow_html=True)
            verdict = "정답입니다." if ss.chosen == answer_idx else "오답입니다."
            st.info(f"**{verdict}** {q['explanation']}")
            if st.button("다음 문제" if ss.pos + 1 < total else "결과 보기", type="primary"):
                ss.pos += 1
                ss.answered = False
                ss.chosen = None
                st.rerun()
    else:
        total = len(ss.queue)
        rate = round(ss.correct_count / total * 100) if total else 0

        if ss.exam_mode:
            st.subheader("실전 시험 모드 결과")
            subj_total = {s: 0 for s in SUBJECTS}
            for qid in ss.queue:
                subj_total[QUESTIONS[qid]["subject"]] += 1

            fail_subjects = []
            rows_html = ""
            for s in SUBJECTS:
                t = subj_total[s]
                c = ss.exam_subject_correct.get(s, 0)
                need = EXAM_MIN_CORRECT[s]
                is_fail = c < need
                if is_fail:
                    fail_subjects.append(s)
                badge_cls = "subj-fail" if is_fail else "subj-ok"
                badge_txt = "과락" if is_fail else "정상"
                rows_html += (
                    f'<div class="subj-row"><span>{SUBJECT_LABEL[s]}</span>'
                    f'<span>{c}/{t}문항 · {c * POINTS_PER_Q}점'
                    f'&nbsp;<span class="subj-badge {badge_cls}">{badge_txt}</span></span></div>'
                )

            total_score = ss.correct_count * POINTS_PER_Q
            overall_pass = (ss.correct_count >= EXAM_TOTAL_PASS) and (len(fail_subjects) == 0)

            if overall_pass:
                st.markdown(
                    f'<div class="exam-pass"><div class="big">합격 예상</div>'
                    f'총점 {total_score}점 / {EXAM_TOTAL_QUESTIONS}점 (정답 {ss.correct_count}/{total})</div>',
                    unsafe_allow_html=True,
                )
            else:
                reason = []
                if ss.correct_count < EXAM_TOTAL_PASS:
                    reason.append(f"총점 미달({total_score}점 &lt; {EXAM_TOTAL_PASS}점)")
                if fail_subjects:
                    reason.append("과락 과목: " + ", ".join(SUBJECT_LABEL[s] for s in fail_subjects))
                st.markdown(
                    f'<div class="exam-fail"><div class="big">불합격 예상</div>'
                    f'총점 {total_score}점 / {EXAM_TOTAL_QUESTIONS}점 (정답 {ss.correct_count}/{total})<br>'
                    f'{" · ".join(reason)}</div>',
                    unsafe_allow_html=True,
                )

            st.markdown("##### 과목별 성적")
            st.markdown(rows_html, unsafe_allow_html=True)
            st.caption(f"합격 기준: 총점 {EXAM_TOTAL_PASS}점 이상 + 과목별 40% 미만(과락) 없음. 실제 채점 기준과 다를 수 있으니 참고용으로 확인하세요.")
        else:
            st.subheader("결과")
            st.metric(f"{ss.quiz_title} 결과", f"{ss.correct_count} / {total}", f"정답률 {rate}%")

        if ss.wrong_ids:
            with st.expander(f"이번 회차 오답 {len(ss.wrong_ids)}개 보기"):
                for wid in ss.wrong_ids:
                    st.markdown(f"- {QUESTIONS[wid]['question']}")
            if st.button("방금 틀린 문제만 다시 풀기"):
                start_quiz(ss.wrong_ids, "방금 틀린 문제")
                st.rerun()
        if st.button("새 퀴즈 시작하기"):
            quit_quiz()
            st.rerun()

# ============ CBT 모드 (실제 기출문제) ============
elif ss.nav == "CBT 모드":
    if ss.cbt_view is None:
        st.subheader("CBT 모드 — 실제 기출문제")
        st.caption(f"정답이 확인된 정보처리기사 기출문제 {len(CBT_IDS)}문항으로 연습합니다 ({'·'.join(str(s) for s in SUBJECTS)}과목).")

        with st.container(border=True):
            st.markdown(f"**실전 모드** — 실제 정보처리기사 필기 출제 기준(과목별 20문항, 총 {EXAM_TOTAL_QUESTIONS}문항)으로 합격/과락 여부까지 진단합니다.")
            st.caption("모든 문제를 푼 뒤 제출 버튼을 누르면 채점되고, 그 이후에 문제별 해설을 볼 수 있어요.")
            if st.button(f"실전 모드 시작 ({EXAM_TOTAL_QUESTIONS}문항)", type="primary", width="stretch"):
                start_cbt("exam", pick_cbt_exam_pool())
                st.rerun()

        st.markdown("#### 연습 모드")
        st.caption("문제마다 힌트·해설을 바로 볼 수 있고, 오답노트에 직접 표시할 수 있어요. 한 번에 채점도 가능합니다.")
        cbt_subject_choice = st.radio("과목 선택", SUBJECT_CHOICES, horizontal=True, key="cbt_subject_choice")
        cbt_count_choice = st.radio("문제 수", ["10문제", "20문제", "전체"], horizontal=True, key="cbt_count_choice")
        if cbt_subject_choice == "전체":
            cbt_subjects = SUBJECTS
        else:
            cbt_subjects = [int(cbt_subject_choice[0])]
        cbt_limit = None if cbt_count_choice == "전체" else int(cbt_count_choice.replace("문제", ""))

        if st.button("연습 모드 시작", width="stretch"):
            start_cbt("practice", pick_cbt_pool(cbt_subjects, cbt_limit))
            st.rerun()

    elif ss.cbt_view == "practice":
        st.subheader("CBT 연습 모드")
        answered_n = sum(1 for qid in ss.cbt_ids if st.session_state.get(f"cbt_ans_{qid}") is not None)
        st.progress(answered_n / len(ss.cbt_ids) if ss.cbt_ids else 0, text=f"응답 {answered_n} / {len(ss.cbt_ids)}")

        if ss.cbt_graded:
            correct_n = sum(
                1 for qid in ss.cbt_ids
                if cbt_selected_index(qid, "cbt_ans") == QUESTIONS[qid]["answer"] - 1
            )
            st.metric("채점 결과", f"{correct_n} / {len(ss.cbt_ids)}")

        for qid in ss.cbt_ids:
            q = QUESTIONS[qid]
            choices = [q["choice1"], q["choice2"], q["choice3"], q["choice4"]]
            answer_idx = q["answer"] - 1
            radio_key = f"cbt_ans_{qid}"
            with st.container(border=True):
                st.markdown(
                    f'<span class="pill">{SUBJECT_LABEL[q["subject"]]}</span>'
                    f'<span class="pill pill-tag">{q["tag"]}</span>'
                    f'<span class="pill pill-src">기출</span>',
                    unsafe_allow_html=True,
                )
                st.markdown(f"**{q['question']}**")
                st.radio(
                    "보기", [f"{CIRCLE[i]} {c}" for i, c in enumerate(choices)],
                    key=radio_key, index=None, label_visibility="collapsed",
                )
                sel_idx = cbt_selected_index(qid, "cbt_ans")

                bcol, fcol = st.columns([1, 1])
                with bcol:
                    reveal = st.button("정답 확인", key=f"cbt_check_{qid}", disabled=sel_idx is None)
                    if reveal:
                        ss.cbt_checked.add(qid)
                with fcol:
                    was_flagged = qid in flagged_ids
                    now_flagged = st.checkbox("오답노트에 추가", value=was_flagged, key=f"cbt_flag_{qid}")
                    if now_flagged and not was_flagged:
                        db.add_flag(con, ss.user, int(qid))
                    elif not now_flagged and was_flagged:
                        db.remove_flag(con, ss.user, int(qid))

                show_feedback = qid in ss.cbt_checked or ss.cbt_graded
                if show_feedback and sel_idx is not None:
                    if qid not in ss.cbt_recorded:
                        db.record_attempt(con, ss.user, int(qid), sel_idx, sel_idx == answer_idx)
                        ss.cbt_recorded.add(qid)
                    verdict = "정답입니다." if sel_idx == answer_idx else f"오답입니다. (정답: {CIRCLE[answer_idx]})"
                    st.info(f"**{verdict}** {q['explanation']}")
                if reveal:
                    st.rerun()

        st.divider()
        if st.button("전체 채점", type="primary", width="stretch"):
            ss.cbt_graded = True
            st.rerun()

    elif ss.cbt_view == "exam":
        st.subheader("CBT 실전 모드")
        answered_n = sum(1 for qid in ss.cbt_ids if st.session_state.get(f"cbtexam_ans_{qid}") is not None)
        st.progress(answered_n / len(ss.cbt_ids) if ss.cbt_ids else 0, text=f"응답 {answered_n} / {len(ss.cbt_ids)}")

        if ss.cbt_submitted:
            total = len(ss.cbt_ids)
            correct_n = sum(
                1 for qid in ss.cbt_ids
                if cbt_selected_index(qid, "cbtexam_ans") == QUESTIONS[qid]["answer"] - 1
            )
            subj_total = {s: 0 for s in SUBJECTS}
            for qid in ss.cbt_ids:
                subj_total[QUESTIONS[qid]["subject"]] += 1

            fail_subjects = []
            rows_html = ""
            for s in SUBJECTS:
                t = subj_total[s]
                c = ss.cbt_exam_subject_correct.get(s, 0)
                need = EXAM_MIN_CORRECT[s]
                is_fail = t > 0 and c < min(need, t)
                if is_fail:
                    fail_subjects.append(s)
                badge_cls = "subj-fail" if is_fail else "subj-ok"
                badge_txt = "과락" if is_fail else "정상"
                rows_html += (
                    f'<div class="subj-row"><span>{SUBJECT_LABEL[s]}</span>'
                    f'<span>{c}/{t}문항 · {c * POINTS_PER_Q}점'
                    f'&nbsp;<span class="subj-badge {badge_cls}">{badge_txt}</span></span></div>'
                )

            total_score = correct_n * POINTS_PER_Q
            overall_pass = (correct_n >= EXAM_TOTAL_PASS) and (len(fail_subjects) == 0)

            if overall_pass:
                st.markdown(
                    f'<div class="exam-pass"><div class="big">합격 예상</div>'
                    f'총점 {total_score}점 / {EXAM_TOTAL_QUESTIONS}점 (정답 {correct_n}/{total})</div>',
                    unsafe_allow_html=True,
                )
            else:
                reason = []
                if correct_n < EXAM_TOTAL_PASS:
                    reason.append(f"총점 미달({total_score}점 &lt; {EXAM_TOTAL_PASS}점)")
                if fail_subjects:
                    reason.append("과락 과목: " + ", ".join(SUBJECT_LABEL[s] for s in fail_subjects))
                st.markdown(
                    f'<div class="exam-fail"><div class="big">불합격 예상</div>'
                    f'총점 {total_score}점 / {EXAM_TOTAL_QUESTIONS}점 (정답 {correct_n}/{total})<br>'
                    f'{" · ".join(reason)}</div>',
                    unsafe_allow_html=True,
                )

            st.markdown("##### 과목별 성적")
            st.markdown(rows_html, unsafe_allow_html=True)
            st.caption(f"합격 기준: 총점 {EXAM_TOTAL_PASS}점 이상 + 과목별 40% 미만(과락) 없음. 실제 채점 기준과 다를 수 있으니 참고용으로 확인하세요.")

        for qid in ss.cbt_ids:
            q = QUESTIONS[qid]
            choices = [q["choice1"], q["choice2"], q["choice3"], q["choice4"]]
            answer_idx = q["answer"] - 1
            radio_key = f"cbtexam_ans_{qid}"
            with st.container(border=True):
                st.markdown(
                    f'<span class="pill">{SUBJECT_LABEL[q["subject"]]}</span>'
                    f'<span class="pill pill-tag">{q["tag"]}</span>'
                    f'<span class="pill pill-src">기출</span>',
                    unsafe_allow_html=True,
                )
                st.markdown(f"**{q['question']}**")
                st.radio(
                    "보기", [f"{CIRCLE[i]} {c}" for i, c in enumerate(choices)],
                    key=radio_key, index=None, label_visibility="collapsed",
                    disabled=ss.cbt_submitted,
                )
                sel_idx = cbt_selected_index(qid, "cbtexam_ans")
                if ss.cbt_submitted and sel_idx is not None:
                    verdict = "정답입니다." if sel_idx == answer_idx else f"오답입니다. (정답: {CIRCLE[answer_idx]})"
                    st.info(f"**{verdict}** {q['explanation']}")

        st.divider()
        if not ss.cbt_submitted:
            if st.button("제출하기", type="primary", width="stretch"):
                subject_correct = {s: 0 for s in SUBJECTS}
                for qid in ss.cbt_ids:
                    sel_idx = cbt_selected_index(qid, "cbtexam_ans")
                    if sel_idx is not None:
                        q = QUESTIONS[qid]
                        is_correct = sel_idx == q["answer"] - 1
                        db.record_attempt(con, ss.user, int(qid), sel_idx, is_correct)
                        if is_correct:
                            subject_correct[q["subject"]] += 1
                ss.cbt_exam_subject_correct = subject_correct
                ss.cbt_submitted = True
                st.rerun()
        else:
            if st.button("새 CBT 세션 시작", width="stretch"):
                quit_cbt()
                st.rerun()

# ============ 개념노트 (카드 / 노트 / OX 퀴즈) ============
elif ss.nav == "개념노트":
    st.subheader("개념노트")
    concepts = get_concepts()

    view_choice = st.radio("보기 방식", ["카드", "노트", "OX 퀴즈"], horizontal=True,
                            index=["카드", "노트", "OX 퀴즈"].index(ss.concept_view))
    if view_choice != ss.concept_view:
        ss.concept_view = view_choice
        ss.card_idx = 0
        ss.card_flipped = False
        ss.ox_pool = None
        st.rerun()

    note_subject = st.radio("과목", SUBJECT_CHOICES, horizontal=True, key="concept_subject")
    if note_subject == "전체":
        note_subjects = SUBJECTS
    else:
        note_subjects = [int(note_subject[0])]
    filtered = [c for c in concepts if c["subject"] in note_subjects]

    if ss.concept_view == "카드":
        if not filtered:
            st.caption("해당 과목의 개념이 없습니다.")
        else:
            ss.card_idx = min(ss.card_idx, len(filtered) - 1)
            c = filtered[ss.card_idx]
            choices = [c["choice1"], c["choice2"], c["choice3"], c["choice4"]]
            answer_idx = c["answer"] - 1
            answer_text = choices[answer_idx]

            card_mode = st.radio(
                "확인 방식", ["뒤집기", "단어 입력형", "빈칸 채우기"], horizontal=True, key="card_mode"
            )
            result_key = f"card_result_{c['id']}_{card_mode}"

            st.progress((ss.card_idx + 1) / len(filtered), text=f"{ss.card_idx + 1} / {len(filtered)}")
            with st.container(border=True):
                st.markdown(
                    f'<span class="pill">{SUBJECT_LABEL[c["subject"]]}</span>'
                    f'<span class="pill pill-tag">{c["tag"]}</span>',
                    unsafe_allow_html=True,
                )

                if card_mode == "뒤집기":
                    st.markdown(f'<div class="qbox">{c["question"]}</div>', unsafe_allow_html=True)
                    if ss.card_flipped:
                        st.markdown(f":green[**정답: {answer_text}**]")
                        st.info(c["explanation"])
                    else:
                        st.caption("정답과 해설을 보려면 아래 버튼을 눌러보세요.")
                else:
                    if card_mode == "단어 입력형":
                        st.markdown(f'<div class="qbox">{c["question"]}</div>', unsafe_allow_html=True)
                    else:
                        blank_sentence = make_blank_sentence(c["explanation"], answer_text)
                        if blank_sentence is None:
                            st.caption("이 개념은 해설에서 빈칸을 만들 수 없어 단어 입력형으로 표시합니다.")
                            st.markdown(f'<div class="qbox">{c["question"]}</div>', unsafe_allow_html=True)
                        else:
                            st.markdown(f'<div class="qbox">{blank_sentence}</div>', unsafe_allow_html=True)
                            hint = " · ".join(f"{CIRCLE[i]} {ch}" for i, ch in enumerate(choices))
                            st.caption(f"보기 중에서 빈칸에 들어갈 말을 골라 입력하세요 — {hint}")

                    result = ss.get(result_key)
                    if result is None:
                        user_ans = st.text_input(
                            "정답 입력", key=f"card_input_{c['id']}_{card_mode}",
                            label_visibility="collapsed", placeholder="정답을 입력하세요",
                        )
                        ic1, ic2 = st.columns([1, 1])
                        with ic1:
                            if st.button("확인", key=f"card_check_{c['id']}_{card_mode}", width="stretch"):
                                is_correct = _answer_matches(user_ans, answer_text)
                                ss[result_key] = is_correct
                                if not is_correct:
                                    db.add_card_wrong(con, ss.user, int(c["id"]))
                                st.rerun()
                        with ic2:
                            if st.button("모르겠어요", key=f"card_skip_{c['id']}_{card_mode}", width="stretch"):
                                ss[result_key] = False
                                db.add_card_wrong(con, ss.user, int(c["id"]))
                                st.rerun()
                    else:
                        if result:
                            st.success(f"정답입니다! **{answer_text}**")
                        else:
                            st.error(f"아쉬워요. 정답은 **{answer_text}** 입니다.")
                        st.info(c["explanation"])
                        if st.button("다시 시도", key=f"card_retry_{c['id']}_{card_mode}"):
                            del ss[result_key]
                            st.rerun()

            b1, b2, b3 = st.columns([1, 1, 1])
            with b1:
                if st.button("◀ 이전", width="stretch", disabled=ss.card_idx == 0):
                    ss.card_idx -= 1
                    ss.card_flipped = False
                    st.rerun()
            with b2:
                if card_mode == "뒤집기":
                    if st.button("정답 보기" if not ss.card_flipped else "다시 가리기", width="stretch", type="primary"):
                        ss.card_flipped = not ss.card_flipped
                        st.rerun()
            with b3:
                if st.button("다음 ▶", width="stretch", disabled=ss.card_idx >= len(filtered) - 1):
                    ss.card_idx += 1
                    ss.card_flipped = False
                    st.rerun()
            if st.button("🔀 순서 섞기"):
                random.shuffle(filtered)
                ss.card_idx = 0
                ss.card_flipped = False
                st.rerun()

            st.divider()
            card_wrong_ids = db.get_card_wrong_ids(con, ss.user)
            if st.button(f"📋 카드 오답 목록 보기 ({len(card_wrong_ids)}개)", width="stretch"):
                ss.card_wrong_view = not ss.card_wrong_view
                st.rerun()
            if ss.card_wrong_view:
                if not card_wrong_ids:
                    st.caption("아직 단어 입력형·빈칸 채우기에서 틀린 개념이 없습니다.")
                else:
                    if st.button("전체 지우기", key="card_wrong_clear_all"):
                        db.clear_card_wrong(con, ss.user)
                        st.rerun()
                    for wqid in card_wrong_ids:
                        wc = QUESTIONS.get(wqid)
                        if wc is None:
                            continue
                        w_answer = [wc["choice1"], wc["choice2"], wc["choice3"], wc["choice4"]][wc["answer"] - 1]
                        with st.container(border=True):
                            st.markdown(
                                f'<span class="pill">{SUBJECT_LABEL[wc["subject"]]}</span>'
                                f'<span class="pill pill-tag">{wc["tag"]}</span>',
                                unsafe_allow_html=True,
                            )
                            st.markdown(f"**{wc['question']}**")
                            st.markdown(f":green[정답: {w_answer}]")
                            st.caption(wc["explanation"])
                            if st.button("목록에서 지우기", key=f"card_wrong_del_{wqid}"):
                                db.clear_card_wrong(con, ss.user, wqid)
                                st.rerun()

    elif ss.concept_view == "노트":
        st.caption(f"{len(filtered)}개 개념을 과목·태그별로 정리했습니다.")
        groups = {}
        for c in filtered:
            groups.setdefault((c["subject"], c["tag"]), []).append(c)
        for (subject, tag), items in groups.items():
            st.markdown(f'<div class="group-title">{SUBJECT_LABEL[subject]} · {tag}</div>', unsafe_allow_html=True)
            for c in items:
                choices = [c["choice1"], c["choice2"], c["choice3"], c["choice4"]]
                answer_idx = c["answer"] - 1
                st.markdown(f"- **{choices[answer_idx]}** — {c['explanation']}")

    else:  # OX 퀴즈
        if ss.ox_pool is None:
            if st.button("OX 퀴즈 시작", type="primary", width="stretch"):
                pool = []
                for c in filtered:
                    choices = [c["choice1"], c["choice2"], c["choice3"], c["choice4"]]
                    correct_idx = c["answer"] - 1
                    is_true = random.random() < 0.5
                    if is_true:
                        statement = choices[correct_idx]
                    else:
                        wrong_idx = random.choice([i for i in range(4) if i != correct_idx])
                        statement = choices[wrong_idx]
                    pool.append({
                        "qid": c["id"], "subject": c["subject"], "tag": c["tag"], "stem": c["question"],
                        "statement": statement, "truth": is_true, "explanation": c["explanation"],
                    })
                random.shuffle(pool)
                ss.ox_pool = pool
                ss.ox_pos = 0
                ss.ox_correct = 0
                ss.ox_answered = False
                ss.ox_choice = None
                st.rerun()
            st.caption("문제 설명이 참(O)인지 거짓(X)인지 빠르게 판단하는 암기 확인 퀴즈입니다. 일반 오답노트에는 기록되지 않고, 틀린 개념만 아래 'OX 오답 목록'에 따로 쌓입니다.")

            st.divider()
            ox_wrong_ids = db.get_ox_wrong_ids(con, ss.user)
            if st.button(f"📋 OX 오답 목록 보기 ({len(ox_wrong_ids)}개)", width="stretch"):
                ss.ox_wrong_view = not ss.ox_wrong_view
                st.rerun()
            if ss.ox_wrong_view:
                if not ox_wrong_ids:
                    st.caption("아직 OX 퀴즈에서 틀린 개념이 없습니다.")
                else:
                    if st.button("전체 지우기", key="ox_wrong_clear_all"):
                        db.clear_ox_wrong(con, ss.user)
                        st.rerun()
                    for wqid in ox_wrong_ids:
                        wc = QUESTIONS.get(wqid)
                        if wc is None:
                            continue
                        w_answer = [wc["choice1"], wc["choice2"], wc["choice3"], wc["choice4"]][wc["answer"] - 1]
                        with st.container(border=True):
                            st.markdown(
                                f'<span class="pill">{SUBJECT_LABEL[wc["subject"]]}</span>'
                                f'<span class="pill pill-tag">{wc["tag"]}</span>',
                                unsafe_allow_html=True,
                            )
                            st.markdown(f"**{wc['question']}**")
                            st.markdown(f":green[정답: {w_answer}]")
                            st.caption(wc["explanation"])
                            if st.button("목록에서 지우기", key=f"ox_wrong_del_{wqid}"):
                                db.clear_ox_wrong(con, ss.user, wqid)
                                st.rerun()
        elif ss.ox_pos < len(ss.ox_pool):
            item = ss.ox_pool[ss.ox_pos]
            total = len(ss.ox_pool)
            st.progress(ss.ox_pos / total, text=f"OX 퀴즈 · {ss.ox_pos + 1} / {total} · 맞음 {ss.ox_correct}")
            with st.container(border=True):
                st.markdown(
                    f'<span class="pill">{SUBJECT_LABEL[item["subject"]]}</span>'
                    f'<span class="pill pill-tag">{item["tag"]}</span>',
                    unsafe_allow_html=True,
                )
                st.markdown(f"**{item['stem']}**")
                st.markdown(f'<div class="qbox">{item["statement"]}</div>', unsafe_allow_html=True)

            if not ss.ox_answered:
                ocol, xcol = st.columns(2)
                with ocol:
                    if st.button("⭕ 맞다(O)", width="stretch"):
                        ss.ox_answered = True
                        ss.ox_choice = True
                        if item["truth"] is True:
                            ss.ox_correct += 1
                        else:
                            db.add_ox_wrong(con, ss.user, item["qid"])
                        st.rerun()
                with xcol:
                    if st.button("❌ 틀리다(X)", width="stretch"):
                        ss.ox_answered = True
                        ss.ox_choice = False
                        if item["truth"] is False:
                            ss.ox_correct += 1
                        else:
                            db.add_ox_wrong(con, ss.user, item["qid"])
                        st.rerun()
            else:
                is_right = ss.ox_choice == item["truth"]
                answer_label = "O(참)" if item["truth"] else "X(거짓)"
                verdict = "맞혔습니다!" if is_right else f"틀렸습니다. 정답은 {answer_label}입니다."
                st.info(f"**{verdict}** {item['explanation']}")
                if st.button("다음" if ss.ox_pos + 1 < total else "결과 보기", type="primary"):
                    ss.ox_pos += 1
                    ss.ox_answered = False
                    ss.ox_choice = None
                    st.rerun()
        else:
            st.subheader("OX 퀴즈 결과")
            total = len(ss.ox_pool)
            rate = round(ss.ox_correct / total * 100) if total else 0
            st.metric("맞은 개수", f"{ss.ox_correct} / {total}", f"정답률 {rate}%")
            if st.button("새 OX 퀴즈 시작하기"):
                ss.ox_pool = None
                st.rerun()

# ============ 오답노트 뷰 (과목·개념별 + 직접 표시한 문제) ============
elif ss.nav == "오답노트":
    st.subheader("오답노트")
    if not need_ids and not done_ids and not flagged_ids:
        st.caption("아직 오답 기록이 없습니다. 퀴즈를 풀면 틀린 문제가 여기에 쌓여요.")
    else:
        if need_ids and st.button(f"복습 필요 {len(need_ids)}개 다시 풀기", type="primary"):
            start_quiz(need_ids, "오답 복습")
            st.rerun()

        _, _, stat_map = db.get_wrong_question_ids(con, ss.user)
        tag_summary = get_tag_summary_map()

        def render_item(qid, show_wrong_meta=True):
            q = QUESTIONS[qid]
            choices = [q["choice1"], q["choice2"], q["choice3"], q["choice4"]]
            answer_idx = q["answer"] - 1
            with st.container(border=True):
                src_pill = '<span class="pill pill-src">기출</span>' if q["source"] == "cbt" else ""
                wrong_badge = ""
                if show_wrong_meta and qid in stat_map:
                    wrong_badge = f'<span style="float:right;color:#C23B33;font-size:.8rem;">오답 {stat_map[qid]["wrong"]}회</span>'
                st.markdown(
                    f'<span class="pill">{SUBJECT_LABEL[q["subject"]]}</span>'
                    f'<span class="pill pill-tag">{q["tag"]}</span>{src_pill}{wrong_badge}',
                    unsafe_allow_html=True,
                )
                st.markdown(f"**{q['question']}**")
                if show_wrong_meta and qid in stat_map:
                    s = stat_map[qid]
                    if s["last_chosen"] is not None and s["last_chosen"] != answer_idx:
                        st.caption(f"마지막 선택: {CIRCLE[s['last_chosen']]} {choices[s['last_chosen']]}")
                st.markdown(f":green[정답: {CIRCLE[answer_idx]} {choices[answer_idx]}]")
                st.caption(q["explanation"])
                bcol1, bcol2 = st.columns([1, 1])
                with bcol1:
                    if show_wrong_meta and qid in stat_map and st.button("풀이 기록 삭제", key=f"clear_{qid}"):
                        db.clear_question_history(con, ss.user, qid)
                        st.rerun()
                with bcol2:
                    if qid in flagged_ids and st.button("표시 해제", key=f"unflag_{qid}"):
                        db.remove_flag(con, ss.user, qid)
                        st.rerun()

        def group_by_subject_tag(ids):
            groups = {}
            for qid in ids:
                q = QUESTIONS[qid]
                key = (q["subject"], q["tag"])
                groups.setdefault(key, []).append(qid)
            return dict(sorted(groups.items(), key=lambda kv: (kv[0][0], kv[0][1])))

        def render_section(title, ids, show_wrong_meta=True):
            if not ids:
                return
            st.markdown(f"### {title} ({len(ids)})")
            groups = group_by_subject_tag(ids)
            for (subject, tag), qids in groups.items():
                st.markdown(f'<div class="group-title">{SUBJECT_LABEL[subject]} · {tag}</div>', unsafe_allow_html=True)
                summary = tag_summary.get((subject, tag))
                if summary:
                    st.markdown(f'<div class="concept-summary">📌 개념 요약: {summary}</div>', unsafe_allow_html=True)
                for qid in qids:
                    render_item(qid, show_wrong_meta=show_wrong_meta)

        render_section("복습 필요", need_ids)
        render_section("복습 완료", done_ids)
        render_section("직접 표시한 문제", [qid for qid in flagged_ids if qid not in need_ids and qid not in done_ids], show_wrong_meta=False)

# ============ 자주 틀리는 개념 뷰 ============
else:
    st.subheader("자주 틀리는 개념")
    st.caption("과목·개념(태그) 단위로 집계합니다.")
    rows = db.get_tag_stats(con, ss.user)
    if not rows:
        st.caption("아직 통계가 부족합니다. 퀴즈를 더 풀어보세요.")
    else:
        max_wrong = max(r["wrong"] for r in rows)
        for r in rows:
            rate = round(r["wrong"] / r["seen"] * 100)
            width = round(r["wrong"] / max_wrong * 100)
            color = "#C23B33" if rate >= 60 else "#B9790E"
            with st.container(border=True):
                st.markdown(
                    f"**{r['tag']}** · {SUBJECT_LABEL[r['subject']]}  \n"
                    f"오답 {r['wrong']} / 시도 {r['seen']} ({rate}%)"
                )
                st.markdown(
                    f'<div class="bar-track"><div class="bar-fill" '
                    f'style="width:{width}%;background:{color};"></div></div>',
                    unsafe_allow_html=True,
                )
                if st.button("이 개념 집중 풀기", key=f"drill_{r['subject']}_{r['tag']}"):
                    start_quiz(list(r["qids"]), f"{r['tag']} 집중풀기")
                    st.rerun()

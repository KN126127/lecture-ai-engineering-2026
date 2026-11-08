"""ツールのテスト（LLMもAPIキーも使わない）。"""

import json

from app import tools


def test_glossary_ids_are_unique_and_related_links_exist():
    terms = tools.load_glossary()
    ids = [t["id"] for t in terms]
    assert len(ids) == len(set(ids))
    for t in terms:
        for r in t["related"]:
            assert r in ids, f"{t['id']} の related に存在しない id: {r}"


def test_search_finds_term_by_name_and_alias():
    for query in ["LoRA", "lora", "Low-Rank Adaptation"]:
        hits = json.loads(tools.search_glossary(query))
        assert hits[0]["term"] == "LoRA", query


def test_search_finds_course_specific_term():
    hits = json.loads(tools.search_glossary("lecNN-start"))
    assert hits[0]["term"] == "lecNN-start タグ"


def test_search_limits_number_of_results():
    hits = json.loads(tools.search_glossary("エージェント"))
    assert 1 <= len(hits) <= tools.MAX_RESULTS


def test_search_reports_not_found():
    assert "見つかりませんでした" in tools.search_glossary("存在しない用語xyz")


def test_lecture_summary():
    assert "エージェント" in tools.get_lecture_summary(3)
    assert "まだありません" in tools.get_lecture_summary(99)


def test_make_quiz_selects_a_term_from_requested_lecture(monkeypatch):
    monkeypatch.setattr(tools.random, "choice", lambda terms: terms[0])

    quiz = tools.make_quiz(3)

    assert "問題:" in quiz
    expected_term = next(term["term"] for term in tools.load_glossary() if term["lecture"] == 3)
    assert f"答え: {expected_term}" in quiz
    assert "第3回" not in quiz


def test_make_quiz_reports_when_lecture_has_no_terms():
    assert "第4回の用語はありません" in tools.make_quiz(4)


def test_learning_log_records_structured_learning_details(tmp_path, monkeypatch):
    monkeypatch.setattr(tools, "LEARNING_LOG_DIR", tmp_path / "learning_log")

    result = tools.save_learning_log(
        summary="LoRA の基本を学んだ",
        question="LoRAとは？",
        answer="少数の追加パラメータでモデルを調整する手法",
        glossary_results="LoRA: 低ランク適応",
        understood_points="元の重みを固定して学習する",
        unresolved_questions="ランクの決め方",
        review_next="QLoRAとの違いを復習する",
        change_description="ツール検索を追加",
        answer_before="定義だけの回答",
        answer_after="定義と例を含む回答",
    )

    log_files = list((tmp_path / "learning_log").glob("*.md"))
    assert len(log_files) == 1
    contents = log_files[0].read_text(encoding="utf-8")
    assert "## " in contents and "JST" in contents
    for expected in [
        "今日のまとめ", "質問", "エージェントの回答", "用語集の結果",
        "理解できたこと", "まだ分からないこと", "次に復習すること",
        "変更内容", "変更前の回答", "変更後の回答", "QLoRAとの違いを復習する",
    ]:
        assert expected in contents
    assert f"learning_log/{log_files[0].name}" in result


def test_get_learning_log_reads_today_and_reports_missing_log(tmp_path, monkeypatch):
    monkeypatch.setattr(tools, "LEARNING_LOG_DIR", tmp_path / "learning_log")
    assert "まだ学習記録がありません" in tools.get_learning_log()

    log_dir = tmp_path / "learning_log"
    log_dir.mkdir()
    today = tools.datetime.now(tools.ZoneInfo("Asia/Tokyo")).strftime("%Y-%m-%d")
    (log_dir / f"{today}.md").write_text("今日の学び", encoding="utf-8")
    assert tools.get_learning_log() == "今日の学び"


def test_save_learning_log_rejects_empty_entry(tmp_path, monkeypatch):
    log_dir = tmp_path / "learning_log"
    monkeypatch.setattr(tools, "LEARNING_LOG_DIR", log_dir)

    assert "空のため保存しませんでした" in tools.save_learning_log("  \n ")
    assert not log_dir.exists()


def test_default_question_of_lecture1_is_answerable_from_glossary():
    """第1回の既定の質問（app.ask）は、第3回のエージェントが用語集で正しく答えられること。"""
    from app.ask import DEFAULT_QUESTION

    assert "3レベル" in DEFAULT_QUESTION
    hits = json.loads(tools.search_glossary("3レベル"))
    assert hits[0]["term"] == "宿題の3レベル"

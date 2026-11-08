"""第3回: エージェントに持たせるツール。

ここに書いた関数の docstring と型ヒントが、そのままモデルへの「ツールの説明文」になる。
説明文を書き換えると、モデルがツールを使うかどうか・どんな引数で呼ぶかが変わる。
"""

import json
import random
from datetime import datetime
from functools import cache
from pathlib import Path
from zoneinfo import ZoneInfo

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
LEARNING_LOG_DIR = Path(__file__).resolve().parent.parent / "learning_log"
MAX_RESULTS = 3


@cache
def load_glossary() -> list[dict]:
    with open(DATA_DIR / "glossary.json", encoding="utf-8") as f:
        return json.load(f)["terms"]


def _normalize(text: str) -> str:
    return text.casefold().replace(" ", "").replace("　", "")


def _names(entry: dict) -> list[str]:
    return [_normalize(entry["term"]), _normalize(entry["id"])] + [
        _normalize(a) for a in entry["aliases"]
    ]


def search_glossary(query: str) -> str:
    """講座の用語集から用語を検索し、定義と、どの回で扱うかを返す。

    AIエンジニアリングの用語や、この講座（AIE2026）に固有の言葉について
    答える前に使うこと。query には調べたい用語を1つだけ入れる（例: "LoRA"）。
    """
    q = _normalize(query)
    if not q:
        return "検索語が空です。調べたい用語を1つ指定してください。"
    glossary = load_glossary()

    exact = [e for e in glossary if q in _names(e)]
    # 「r」のような短い別名が何にでも当たらないよう、名前側が短いものは除く
    partial = [
        e for e in glossary
        if e not in exact and any(q in n or (len(n) >= 3 and n in q) for n in _names(e))
    ]
    in_definition = [
        e for e in glossary
        if e not in exact and e not in partial and q in _normalize(e["definition"])
    ]
    hits = (exact + partial + in_definition)[:MAX_RESULTS]

    if not hits:
        return f"用語集に「{query}」は見つかりませんでした。"
    return json.dumps(
        [
            {
                "term": e["term"],
                "lecture": e["lecture"],
                "definition": e["definition"],
                "related": e["related"],
            }
            for e in hits
        ],
        ensure_ascii=False,
    )


def get_lecture_summary(lecture: int) -> str:
    """指定した回（1始まりの整数）の講義の要点を返す。

    「第3回では何を学ぶ？」のように、回の内容や関係を聞かれたときに使う。
    """
    path = DATA_DIR / "lectures" / f"{lecture:02d}.md"
    if not path.exists():
        available = sorted(p.stem for p in (DATA_DIR / "lectures").glob("*.md"))
        return f"第{lecture}回の要点はまだありません。用意されている回: {', '.join(available)}"
    return path.read_text(encoding="utf-8")


def make_quiz(lecture: int) -> str:
    """指定した回の用語から1つ選び、確認問題と答えを返す。

    用語の定義から用語名を答える問題を作る。講義内容の理解を確認したいときに使う。
    """
    terms = [term for term in load_glossary() if term["lecture"] == lecture]
    if not terms:
        available = sorted({term["lecture"] for term in load_glossary()})
        return f"第{lecture}回の用語はありません。用語がある回: {', '.join(map(str, available))}"

    term = random.choice(terms)
    return f"問題: 次の説明に当てはまる用語は何ですか？\n{term['definition']}\n答え: {term['term']}"


def get_learning_log() -> str:
    """今日すでに保存した学習記録を返す。

    今日学んだことの振り返りや、今日の記録をまとめる依頼に使う。
    """
    now = datetime.now(ZoneInfo("Asia/Tokyo"))
    log_path = LEARNING_LOG_DIR / f"{now:%Y-%m-%d}.md"
    if not log_path.exists():
        return "今日はまだ学習記録がありません。"
    return log_path.read_text(encoding="utf-8")


def save_learning_log(
    summary: str,
    question: str = "",
    answer: str = "",
    glossary_results: str = "",
    understood_points: str = "",
    unresolved_questions: str = "",
    review_next: str = "",
    change_description: str = "",
    answer_before: str = "",
    answer_after: str = "",
) -> str:
    """学習内容を項目別に日付ごとのログへ追記する。

    保存を明示的に頼まれたときに使う。現在の質問と回答、用語集の結果、
    理解した点、未解決の疑問、次に復習することを分かる範囲で記録する。
    指示やツールの変更前後を比較する場合は、変更内容と両方の回答も記録する。
    根拠がない項目は空のままにする。
    """
    if not summary.strip():
        return "学習記録が空のため保存しませんでした。"

    now = datetime.now(ZoneInfo("Asia/Tokyo"))
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S %Z")
    log_path = LEARNING_LOG_DIR / f"{now:%Y-%m-%d}.md"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    sections = [
        ("今日のまとめ", summary),
        ("質問", question),
        ("エージェントの回答", answer),
        ("用語集の結果", glossary_results),
        ("理解できたこと", understood_points),
        ("まだ分からないこと", unresolved_questions),
        ("次に復習すること", review_next),
        ("変更内容", change_description),
        ("変更前の回答", answer_before),
        ("変更後の回答", answer_after),
    ]
    record = [f"## {timestamp}"]
    for heading, value in sections:
        if value.strip():
            record.extend(["", f"### {heading}", value.strip()])
    with log_path.open("a", encoding="utf-8") as f:
        f.write("\n".join(record) + "\n\n")
    return f"学習記録を learning_log/{log_path.name} に保存しました。"

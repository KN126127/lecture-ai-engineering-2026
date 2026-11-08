"""エージェントの配線テスト。

TestModel は実際のLLMを呼ばない偽モデルで、登録されたツールを全部呼んでから
ダミーの回答を返す。APIキーも利用枠も使わずに、
「ツールが登録され、呼ばれ、結果がモデルに戻るか」を確かめられる。
"""

import pytest
from pydantic_ai import DeferredToolRequests
from pydantic_ai.messages import ToolCallPart, ToolReturnPart
from pydantic_ai.models.test import TestModel

from app import tools
from app.agent import (
    agent,
    load_conversation_history,
    run_with_approval,
    save_conversation_history,
)

BASE_TOOLS = {"search_glossary", "get_lecture_summary"}


def _parts(result, kind):
    return [p for m in result.all_messages() for p in m.parts if isinstance(p, kind)]


def test_base_tools_are_registered_and_called():
    model = TestModel(call_tools=["search_glossary", "get_lecture_summary"])
    with agent.override(model=model):
        result = agent.run_sync("LoRAとは？")

    offered = {t.name for t in model.last_model_request_parameters.function_tools}
    assert BASE_TOOLS <= offered  # 演習でツールを足しても壊れないよう「含む」で判定
    assert "get_learning_log" in offered
    assert "save_learning_log" in offered

    called = {p.tool_name for p in _parts(result, ToolCallPart)}
    assert BASE_TOOLS <= called
    assert len(_parts(result, ToolReturnPart)) == len(_parts(result, ToolCallPart))
    assert result.output


def test_glossary_result_reaches_the_model():
    model = TestModel(call_tools=["search_glossary"])
    with agent.override(model=model):
        result = agent.run_sync("RAGとは？")
    returns = _parts(result, ToolReturnPart)
    assert returns and returns[0].tool_name == "search_glossary"


def test_save_learning_log_waits_for_approval():
    model = TestModel(call_tools=["save_learning_log"])
    with agent.override(model=model):
        result = agent.run_sync("この内容を学習記録として保存して", model=model)

    assert isinstance(result.output, DeferredToolRequests)
    assert [call.tool_name for call in result.output.approvals] == ["save_learning_log"]


@pytest.mark.parametrize("answer, saved", [("y", True), ("n", False)])
def test_cli_resumes_after_approval_decision(tmp_path, monkeypatch, answer, saved):
    monkeypatch.setattr(tools, "LEARNING_LOG_DIR", tmp_path / "learning_log")
    monkeypatch.setattr("builtins.input", lambda _: answer)
    model = TestModel(call_tools=["save_learning_log"])

    with agent.override(model=model):
        result = run_with_approval(agent, "この内容を学習記録として保存して", model)

    assert isinstance(result.output, str)
    log_files = list((tmp_path / "learning_log").glob("*.md"))
    assert bool(log_files) is saved


def test_conversation_history_is_persisted_and_resumed(tmp_path):
    history_path = tmp_path / "conversation.json"
    model = TestModel(call_tools=[])

    first = agent.run_sync("最初の質問", model=model)
    save_conversation_history(history_path, first.all_messages_json())
    history = load_conversation_history(history_path)
    second = agent.run_sync("過去の質問を要約して", model=model, message_history=history)

    assert len(history) == len(first.all_messages())
    assert len(second.all_messages()) > len(history)
    assert second.all_messages()[:len(history)] == history

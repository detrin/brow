from benchmarks.harness.tools_common import SUBMIT_ANSWER_TOOL, execute_submit_answer

def test_submit_answer_schema():
    assert SUBMIT_ANSWER_TOOL["name"] == "submit_answer"
    assert "input_schema" in SUBMIT_ANSWER_TOOL
    props = SUBMIT_ANSWER_TOOL["input_schema"]["properties"]
    assert "answer" in props
    assert "confidence" in props

def test_execute_submit_answer():
    result = execute_submit_answer({"answer": {"title": "test"}, "confidence": "high"})
    assert result["done"] is True
    assert result["answer"]["title"] == "test"

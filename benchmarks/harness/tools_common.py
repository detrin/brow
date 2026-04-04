SUBMIT_ANSWER_TOOL = {
    "name": "submit_answer",
    "description": "Submit your final answer for the task. Call this when you have completed the task.",
    "input_schema": {
        "type": "object",
        "properties": {
            "answer": {"type": "object", "description": "Structured result matching task requirements"},
            "confidence": {"type": "string", "enum": ["high", "medium", "low"], "description": "Your confidence in the answer"},
        },
        "required": ["answer"],
    },
}

def execute_submit_answer(params):
    import json
    answer = params.get("answer", {})
    # Claude sometimes passes a JSON string instead of a parsed object — fix it here.
    if isinstance(answer, str):
        try:
            answer = json.loads(answer)
        except (json.JSONDecodeError, ValueError):
            answer = {"result": answer}
    return {"done": True, "answer": answer, "confidence": params.get("confidence", "medium")}

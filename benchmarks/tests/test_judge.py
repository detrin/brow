from benchmarks.harness.judge import evaluate_criteria

def test_structured_output_pass():
    criteria = {"type": "structured_output", "min_fields": ["title", "url"], "min_results": 2}
    answer = {"results": [{"title": "A", "url": "http://a"}, {"title": "B", "url": "http://b"}]}
    assert evaluate_criteria(criteria, answer, {}) is True

def test_structured_output_missing_field():
    criteria = {"type": "structured_output", "min_fields": ["title", "url"], "min_results": 1}
    answer = {"results": [{"title": "A"}]}
    assert evaluate_criteria(criteria, answer, {}) is False

def test_structured_output_too_few():
    criteria = {"type": "structured_output", "min_fields": ["title"], "min_results": 5}
    answer = {"results": [{"title": "A"}, {"title": "B"}]}
    assert evaluate_criteria(criteria, answer, {}) is False

def test_url_match_pass():
    criteria = {"type": "url_match", "pattern": r"example\.com/dashboard"}
    assert evaluate_criteria(criteria, {}, {"url": "https://example.com/dashboard?tab=1"}) is True

def test_url_match_fail():
    criteria = {"type": "url_match", "pattern": r"example\.com/admin"}
    assert evaluate_criteria(criteria, {}, {"url": "https://example.com/dashboard"}) is False

def test_no_errors_pass():
    criteria = {"type": "no_errors"}
    assert evaluate_criteria(criteria, {}, {}, errors=[]) is True

def test_no_errors_fail():
    criteria = {"type": "no_errors"}
    assert evaluate_criteria(criteria, {}, {}, errors=["timeout"]) is False

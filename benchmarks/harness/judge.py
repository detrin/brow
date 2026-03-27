import importlib
import re

def evaluate_criteria(criteria, answer, browser_state, errors=None):
    ctype = criteria["type"]
    if ctype == "structured_output":
        return _check_structured_output(criteria, answer)
    if ctype == "url_match":
        return _check_url_match(criteria, browser_state)
    if ctype == "no_errors":
        return len(errors or []) == 0
    if ctype == "element_visible":
        return browser_state.get("element_visible", False)
    if ctype == "custom":
        return _check_custom(criteria, answer, browser_state)
    return False

def _check_structured_output(criteria, answer):
    min_fields = criteria.get("min_fields", [])
    min_results = criteria.get("min_results", 1)
    results = _find_results_list(answer)
    if len(results) < min_results:
        return False
    for item in results:
        if not all(f in item for f in min_fields):
            return False
    return True

def _find_results_list(answer):
    if isinstance(answer, list):
        return answer
    if isinstance(answer, dict):
        for v in answer.values():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                return v
        # If no nested list found, treat the dict itself as a single result
        return [answer]
    return []

def _check_url_match(criteria, browser_state):
    pattern = criteria.get("pattern", "")
    url = browser_state.get("url", "")
    return bool(re.search(pattern, url))

def _check_custom(criteria, answer, browser_state):
    func_path = criteria.get("function", "")
    module_path, func_name = func_path.rsplit(".", 1)
    mod = importlib.import_module(module_path)
    func = getattr(mod, func_name)
    return func(answer, browser_state)

def evaluate_all(criteria_list, answer, browser_state, errors=None):
    return all(evaluate_criteria(c, answer, browser_state, errors) for c in criteria_list)

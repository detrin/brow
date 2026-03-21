import re
from brow.snapshot import format_tree, filter_lines

SAMPLE_TREE = {
    "role": "WebArea",
    "name": "Example",
    "children": [
        {"role": "heading", "name": "Hello", "level": 1},
        {"role": "link", "name": "Click me"},
        {"role": "textbox", "name": "Email"},
    ]
}

def test_format_tree():
    result = format_tree(SAMPLE_TREE)
    assert "heading" in result
    assert "Hello" in result
    assert "link" in result

def test_format_tree_none():
    assert format_tree(None) == ""

def test_filter_lines():
    text = "line one\nline two\nline three"
    result = filter_lines(text, "two")
    assert "two" in result
    assert "one" not in result

def test_filter_lines_regex():
    text = "apple 1\nbanana 2\napricot 3"
    result = filter_lines(text, "^ap")
    assert "apple" in result
    assert "apricot" in result
    assert "banana" not in result

def test_filter_lines_limit():
    text = "\n".join(f"match {i}" for i in range(20))
    result = filter_lines(text, "match", limit=10)
    lines = [l for l in result.strip().split("\n") if l]
    assert len(lines) == 10

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

def test_format_tree_with_ref():
    tree = {"role": "heading", "name": "Title", "level": 1}
    result = format_tree(tree)
    assert "[" not in result

    interactive_tree = {"role": "button", "name": "Submit", "ref": 1}
    result = format_tree(interactive_tree)
    assert "[1]" in result
    assert 'button "Submit"' in result

def test_format_tree_multiple_refs():
    tree = {
        "role": "WebArea", "name": "Page",
        "children": [
            {"role": "link", "name": "Home", "href": "/", "ref": 1},
            {"role": "heading", "name": "Welcome", "level": 1},
            {"role": "textbox", "name": "Email", "ref": 2},
            {"role": "button", "name": "Submit", "ref": 3},
        ],
    }
    result = format_tree(tree)
    lines = result.strip().split("\n")
    assert "[1]" in lines[1]
    assert "[" not in lines[2]
    assert "[2]" in lines[3]
    assert "[3]" in lines[4]

def test_filter_lines_limit():
    text = "\n".join(f"match {i}" for i in range(20))
    result = filter_lines(text, "match", limit=10)
    lines = [l for l in result.strip().split("\n") if l]
    assert len(lines) == 10

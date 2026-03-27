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

def test_format_tree_table():
    tree = {
        "role": "table",
        "headers": ["Name", "Price", "Rating"],
        "rows": [
            ["Widget A", "$10", "4.5"],
            ["Widget B", "$20", "4.8"],
            ["Widget C", "$30", "4.2"],
        ],
        "totalRows": 3,
    }
    result = format_tree(tree)
    assert "| Name | Price | Rating |" in result
    assert "| Widget A | $10 | 4.5 |" in result
    assert "| Widget C | $30 | 4.2 |" in result


def test_format_tree_table_truncated():
    tree = {
        "role": "table",
        "headers": ["Name", "Price"],
        "rows": [["Item " + str(i), "$" + str(i)] for i in range(10)],
        "totalRows": 50,
    }
    result = format_tree(tree)
    assert "| Name | Price |" in result
    assert "40 more rows" in result


def test_format_tree_table_no_headers():
    tree = {
        "role": "table",
        "headers": [],
        "rows": [["A", "B"], ["C", "D"]],
        "totalRows": 2,
    }
    result = format_tree(tree)
    assert "A" in result
    assert "C" in result


def test_format_tree_inline_list():
    tree = {
        "role": "inline-list",
        "itemRole": "link",
        "items": [
            {"role": "link", "name": "Home", "href": "/", "ref": 1},
            {"role": "link", "name": "About", "href": "/about", "ref": 2},
            {"role": "link", "name": "Products", "href": "/products", "ref": 3},
            {"role": "link", "name": "Blog", "href": "/blog", "ref": 4},
            {"role": "link", "name": "Contact", "href": "/contact", "ref": 5},
            {"role": "link", "name": "Help", "href": "/help", "ref": 6},
        ],
    }
    result = format_tree(tree)
    assert "[1]" in result
    assert "[6]" in result
    assert "|" in result
    lines = result.strip().split("\n")
    assert len(lines) == 1


def test_format_tree_inline_list_no_refs():
    tree = {
        "role": "inline-list",
        "itemRole": "li",
        "items": [
            {"role": "li", "name": "Item A"},
            {"role": "li", "name": "Item B"},
            {"role": "li", "name": "Item C"},
            {"role": "li", "name": "Item D"},
            {"role": "li", "name": "Item E"},
            {"role": "li", "name": "Item F"},
        ],
    }
    result = format_tree(tree)
    assert "Item A" in result
    assert "Item F" in result
    assert "|" in result


def test_filter_lines_limit():
    text = "\n".join(f"match {i}" for i in range(20))
    result = filter_lines(text, "match", limit=10)
    lines = [l for l in result.strip().split("\n") if l]
    assert len(lines) == 10

"""Tests for the insert_block_tree tool."""
from unittest.mock import MagicMock

import mcp_logseq.tools as tools

TREE = """- Candidate A
  - Status: Progress
  - Review notes
    - Strengths
      - Point one
      - Point two
- Candidate B
  - Status: Reject"""


def _run(args, result=None, parent_children=None):
    api = MagicMock()
    api.insert_batch_block.return_value = result
    api.get_block.return_value = {"uuid": "p1", "children": parent_children or []}
    out = tools.InsertBlockTreeToolHandler()._run(api, args)
    return api, out[0].text


def test_inserts_nested_tree_as_children_in_one_call():
    api, text = _run({"parent_block_uuid": "p1", "content": TREE})
    api.insert_batch_block.assert_called_once()
    anchor, blocks = api.insert_batch_block.call_args.args[:2]
    assert anchor == "p1"  # parent has no children yet -> insert directly as children
    assert api.insert_batch_block.call_args.kwargs == {"sibling": False}
    assert [b["content"] for b in blocks] == ["Candidate A", "Candidate B"]
    a = blocks[0]["children"]
    assert [c["content"] for c in a] == ["Status: Progress", "Review notes"]
    strengths = a[1]["children"][0]
    assert strengths["content"] == "Strengths"
    assert [c["content"] for c in strengths["children"]] == ["Point one", "Point two"]
    assert "Inserted 8 block(s) (2 top-level) as children of p1" in text


def test_sibling_mode():
    api, text = _run({"parent_block_uuid": "p1", "content": "- One\n- Two", "sibling": True})
    api.get_block.assert_not_called()
    assert api.insert_batch_block.call_args.args[0] == "p1"
    assert api.insert_batch_block.call_args.kwargs == {"sibling": True}
    assert "siblings after p1" in text


def test_headings_kept_in_content():
    api, _ = _run({"parent_block_uuid": "p1", "content": "- ### Name\n  - child"})
    blocks = api.insert_batch_block.call_args.args[1]
    assert blocks[0]["content"] == "### Name"
    assert blocks[0]["children"][0]["content"] == "child"


def test_reports_top_level_uuids_from_flat_depth_first_result():
    # Logseq returns all 8 created blocks flat, depth-first
    contents = ["Candidate A", "Status: Progress", "Review notes", "Strengths",
                "Point one", "Point two", "Candidate B", "Status: Reject"]
    result = [{"uuid": f"u{i}", "content": c} for i, c in enumerate(contents)]
    _, text = _run({"parent_block_uuid": "p1", "content": TREE}, result=result)
    assert "- u0  Candidate A" in text
    assert "- u6  Candidate B" in text
    assert "Status: Progress" not in text.split("Top-level block UUIDs:")[1]


def test_no_uuid_list_when_result_shape_unexpected():
    _, text = _run({"parent_block_uuid": "p1", "content": TREE}, result=[{"uuid": "x"}])
    assert "Top-level block UUIDs" not in text


def test_appends_after_last_existing_child():
    api, _ = _run({"parent_block_uuid": "p1", "content": "- New"},
                  parent_children=[["uuid", "c1"], ["uuid", "c2"]])
    api.get_block.assert_called_once_with("p1", include_children=False)
    anchor = api.insert_batch_block.call_args.args[0]
    assert anchor == "c2"
    assert api.insert_batch_block.call_args.kwargs == {"sibling": True}


def test_appends_after_last_child_when_children_expanded():
    api, _ = _run({"parent_block_uuid": "p1", "content": "- New"},
                  parent_children=[{"uuid": "c1"}, {"uuid": "c9"}])
    assert api.insert_batch_block.call_args.args[0] == "c9"


def test_empty_content_rejected():
    api, text = _run({"parent_block_uuid": "p1", "content": "   "})
    api.insert_batch_block.assert_not_called()
    assert "No blocks" in text


def test_frontmatter_rejected():
    api, text = _run({"parent_block_uuid": "p1", "content": "---\ntags: x\n---\n- One"})
    api.insert_batch_block.assert_not_called()
    assert "frontmatter" in text


def test_api_error_reported():
    api = MagicMock()
    api.insert_batch_block.side_effect = RuntimeError("boom")
    text = tools.InsertBlockTreeToolHandler()._run(api, {"parent_block_uuid": "p1", "content": "- One"})[0].text
    assert "Failed to insert block tree" in text and "boom" in text

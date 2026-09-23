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


def _run(args, result=None):
    api = MagicMock()
    api.insert_batch_block.return_value = result
    out = tools.InsertBlockTreeToolHandler()._run(api, args)
    return api, out[0].text


def test_inserts_nested_tree_as_children_in_one_call():
    api, text = _run({"parent_block_uuid": "p1", "content": TREE})
    api.insert_batch_block.assert_called_once()
    anchor, blocks = api.insert_batch_block.call_args.args[:2]
    assert anchor == "p1"
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
    assert api.insert_batch_block.call_args.kwargs == {"sibling": True}
    assert "siblings after p1" in text


def test_headings_kept_in_content():
    api, _ = _run({"parent_block_uuid": "p1", "content": "- ### Name\n  - child"})
    blocks = api.insert_batch_block.call_args.args[1]
    assert blocks[0]["content"] == "### Name"
    assert blocks[0]["children"][0]["content"] == "child"


def test_reports_top_level_uuids_when_returned():
    result = [{"uuid": "u-a", "content": "Candidate A"}, {"uuid": "u-b", "content": "Candidate B"}]
    _, text = _run({"parent_block_uuid": "p1", "content": TREE}, result=result)
    assert "- u-a  Candidate A" in text
    assert "- u-b  Candidate B" in text


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

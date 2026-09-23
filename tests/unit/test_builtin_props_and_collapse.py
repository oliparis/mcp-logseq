"""Tests for built-in property idents in set_block_properties and set_block_collapsed."""
from unittest.mock import MagicMock, patch

import mcp_logseq.tools as tools


def _run(handler, args):
    api = MagicMock()
    with patch("mcp_logseq.tools._make_api", return_value=api), \
         patch("mcp_logseq.tools._get_db_mode", return_value=True):
        out = handler._run(api, args)
    return api, out[0].text


def test_full_ident_bypasses_lookup():
    api, text = _run(tools.SetBlockPropertiesToolHandler(),
                     {"block_uuid": "u1", "properties": {":logseq.property/background-color": "green"}})
    api.resolve_property_ident.assert_not_called()
    api._upsert_block_property.assert_called_once_with("u1", ":logseq.property/background-color", "green")
    assert "✅" in text


def test_display_name_still_resolved():
    api = MagicMock()
    api.resolve_property_ident.return_value = ":user.property/Status-abc"
    with patch("mcp_logseq.tools._get_db_mode", return_value=True):
        tools.SetBlockPropertiesToolHandler()._run(api, {"block_uuid": "u1", "properties": {"Status": "x"}})
    api._upsert_block_property.assert_called_once_with("u1", ":user.property/Status-abc", "x")


def test_set_block_collapsed_default_true():
    api, text = _run(tools.SetBlockCollapsedToolHandler(), {"block_uuid": "u2"})
    api.set_block_collapsed.assert_called_once_with("u2", True)
    assert "collapsed" in text


def test_set_block_collapsed_expand():
    api, text = _run(tools.SetBlockCollapsedToolHandler(), {"block_uuid": "u2", "collapsed": False})
    api.set_block_collapsed.assert_called_once_with("u2", False)
    assert "expanded" in text

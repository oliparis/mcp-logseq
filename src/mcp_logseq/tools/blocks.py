"""Block-level tool handlers (delete, update, get, insert nested, set properties)."""

import json

from mcp.types import Tool, TextContent

import mcp_logseq.tools as _t
from .. import access, parser
from .base import ToolHandler, logger
# GetBlock reuses GetPageContent's block-tree formatter.
from .pages import GetPageContentToolHandler


class DeleteBlockToolHandler(ToolHandler):
    access_policy = [
        access.BlockNamespace("block_uuid"),
        access.BlockTag("block_uuid"),
    ]

    def __init__(self):
        super().__init__("delete_block")

    def get_tool_description(self):
        return Tool(
            name=self.name,
            description="Delete a block from LogSeq by its UUID.",
            input_schema={
                "type": "object",
                "properties": {
                    "block_uuid": {
                        "type": "string",
                        "description": "UUID of the block to delete"
                    }
                },
                "required": ["block_uuid"]
            }
        )

    def _run(self, api, args: dict) -> list[TextContent]:
        if "block_uuid" not in args:
            raise RuntimeError("block_uuid argument required")

        block_uuid = args["block_uuid"]

        try:
            api.delete_block(block_uuid)

            return [TextContent(
                type="text",
                text=f"✅ Successfully deleted block '{block_uuid}'"
            )]
        except ValueError as e:
            return [TextContent(
                type="text",
                text=f"❌ Error: {str(e)}"
            )]
        except Exception as e:
            logger.error(f"Failed to delete block: {str(e)}")
            return [TextContent(
                type="text",
                text=f"❌ Failed to delete block '{block_uuid}': {str(e)}"
            )]


class UpdateBlockToolHandler(ToolHandler):
    access_policy = [
        access.BlockNamespace("block_uuid"),
        access.BlockTag("block_uuid"),
    ]

    def __init__(self):
        super().__init__("update_block")

    def get_tool_description(self):
        return Tool(
            name=self.name,
            description="Update the content of an existing LogSeq block by UUID.",
            input_schema={
                "type": "object",
                "properties": {
                    "block_uuid": {
                        "type": "string",
                        "description": "UUID of the block to update"
                    },
                    "content": {
                        "type": "string",
                        "description": "New content that replaces the block text"
                    }
                },
                "required": ["block_uuid", "content"]
            }
        )

    def _run(self, api, args: dict) -> list[TextContent]:
        if "block_uuid" not in args or "content" not in args:
            raise RuntimeError("block_uuid and content arguments required")

        block_uuid = args["block_uuid"]
        content = args["content"]

        try:
            api.update_block(block_uuid, content)

            return [TextContent(
                type="text",
                text=f"✅ Successfully updated block '{block_uuid}'"
            )]
        except ValueError as e:
            return [TextContent(
                type="text",
                text=f"❌ Error: {str(e)}"
            )]
        except Exception as e:
            logger.error(f"Failed to update block: {str(e)}")
            return [TextContent(
                type="text",
                text=f"❌ Failed to update block '{block_uuid}': {str(e)}"
            )]


class GetBlockToolHandler(ToolHandler):
    """Retrieve a single block by UUID, including its content, properties, and children."""

    access_policy = [
        access.BlockNamespace("block_uuid"),
        access.BlockTag("block_uuid"),
    ]

    def __init__(self):
        super().__init__("get_block")

    def get_tool_description(self):
        return Tool(
            name=self.name,
            description="Get a single block by its UUID. Returns the block content, properties, and child blocks (recursively). Useful for inspecting a specific block after finding its UUID via search or query.",
            input_schema={
                "type": "object",
                "properties": {
                    "block_uuid": {
                        "type": "string",
                        "description": "UUID of the block to retrieve",
                    },
                    "include_children": {
                        "type": "boolean",
                        "description": "Whether to include child blocks recursively (default: true)",
                        "default": True,
                    },
                    "format": {
                        "type": "string",
                        "description": "Output format (text or json)",
                        "enum": ["text", "json"],
                        "default": "text",
                    },
                },
                "required": ["block_uuid"],
            },
        )

    def _run(self, api, args: dict) -> list[TextContent]:
        if "block_uuid" not in args:
            raise RuntimeError("block_uuid argument required")

        block_uuid = args["block_uuid"]
        include_children = args.get("include_children", True)
        output_format = args.get("format", "text")

        try:
            result = api.get_block(block_uuid, include_children=include_children)

            if output_format == "json":
                return [TextContent(type="text", text=json.dumps(result, indent=2))]

            # Format as readable text using the same tree formatter as get_page_content
            content_parts = []

            # Fetch DB-mode class properties when enabled
            db_properties = {}
            if _t._get_db_mode():
                try:
                    db_properties = api.get_blocks_db_properties([result])
                    logger.info(f"DB-mode properties found for {len(db_properties)} blocks")
                except Exception as e:
                    logger.warning(f"Could not fetch DB-mode properties: {e}")

            block_lines = GetPageContentToolHandler._format_block_tree(
                result, 0, -1, db_properties
            )
            content_parts.extend(block_lines)

            if not content_parts:
                return [TextContent(
                    type="text",
                    text=f"Block '{block_uuid}' exists but has no content.",
                )]

            return [TextContent(type="text", text="\n".join(content_parts))]

        except ValueError as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]
        except Exception as e:
            logger.error(f"Failed to get block: {str(e)}")
            return [TextContent(
                type="text",
                text=f"Failed to get block '{block_uuid}': {str(e)}",
            )]


class InsertNestedBlockToolHandler(ToolHandler):
    access_policy = [
        access.BlockNamespace("parent_block_uuid"),
        access.BlockTag("parent_block_uuid"),
    ]

    def __init__(self):
        super().__init__("insert_nested_block")

    def get_tool_description(self):
        return Tool(
            name=self.name,
            description="""Insert a new block as a child or sibling of an existing block, enabling nested hierarchical structures""",
            input_schema={
                "type": "object",
                "properties": {
                    "parent_block_uuid": {
                        "type": "string",
                        "description": "UUID of the reference block. If sibling=false, new block becomes a CHILD of this UUID. If sibling=true, new block becomes a SIBLING of this UUID (at the same level)."
                    },
                    "content": {
                        "type": "string",
                        "description": "Content text for the new block"
                    },
                    "properties": {
                        "type": "object",
                        "description": "Optional block properties (e.g., {'marker': 'TODO', 'priority': 'A'})",
                        "additionalProperties": True
                    },
                    "sibling": {
                        "type": "boolean",
                        "description": "false (default) = insert as CHILD under parent_block_uuid. true = insert as SIBLING after parent_block_uuid at the same level. For multiple children under same parent, ALWAYS use false with the parent's UUID.",
                        "default": False
                    }
                },
                "required": ["parent_block_uuid", "content"]
            }
        )

    def _run(self, api, args: dict) -> list[TextContent]:
        """Insert a nested block under an existing block."""
        if "parent_block_uuid" not in args or "content" not in args:
            raise RuntimeError("parent_block_uuid and content arguments required")

        parent_uuid = args["parent_block_uuid"]
        content = args["content"]
        properties = args.get("properties")
        sibling = args.get("sibling", False)

        try:
            result = api.insert_block_as_child(
                parent_block_uuid=parent_uuid,
                content=content,
                properties=properties,
                sibling=sibling
            )

            relationship = "sibling" if sibling else "child"
            success_msg = f"✅ Successfully inserted block as {relationship}"

            # Add block details if available
            if result and isinstance(result, dict):
                if result.get("uuid"):
                    success_msg += f"\n🆔 New block UUID: {result.get('uuid')}"
                if result.get("content"):
                    content_preview = result.get('content')
                    if len(content_preview) > 100:
                        content_preview = content_preview[:100] + "..."
                    success_msg += f"\n📝 Content: {content_preview}"

            success_msg += f"\n🔗 Inserted under parent: {parent_uuid}"

            return [TextContent(
                type="text",
                text=success_msg
            )]

        except ValueError as e:
            return [TextContent(
                type="text",
                text=f"❌ Error: {str(e)}"
            )]
        except Exception as e:
            logger.error(f"Failed to insert nested block: {str(e)}")
            return [TextContent(
                type="text",
                text=f"❌ Failed to insert nested block: {str(e)}"
            )]


class SetBlockPropertiesToolHandler(ToolHandler):
    access_policy = [
        access.BlockNamespace("block_uuid"),
        access.BlockTag("block_uuid"),
    ]

    def __init__(self):
        super().__init__("set_block_properties")

    def get_tool_description(self):
        return Tool(
            name=self.name,
            description="Set properties on a block in Logseq DB-mode. Use user property display names (e.g. 'Content status'), or a full ident starting with ':' for built-in properties (e.g. ':logseq.property/background-color': 'green', ':logseq.property/heading': 3).",
            input_schema={
                "type": "object",
                "properties": {
                    "block_uuid": {
                        "type": "string",
                        "description": "UUID of the block to update",
                    },
                    "properties": {
                        "type": "object",
                        "description": "Properties to set as {name: value} pairs. Use display names (e.g. 'Content status': 'kiem')",
                        "additionalProperties": True,
                    },
                },
                "required": ["block_uuid", "properties"],
            },
        )

    def _run(self, api, args: dict) -> list[TextContent]:
        """Set DB-mode properties on a block."""
        if not _t._get_db_mode():
            return [TextContent(
                type="text",
                text="❌ set_block_properties requires LOGSEQ_DB_MODE=true (only works with Logseq DB-mode graphs)",
            )]

        if "block_uuid" not in args or "properties" not in args:
            raise RuntimeError("block_uuid and properties arguments required")

        block_uuid = args["block_uuid"]
        properties = args["properties"]

        try:
            results = []

            for prop_name, value in properties.items():
                # Full idents (e.g. ':logseq.property/background-color') are
                # passed straight through so built-in properties can be set;
                # otherwise resolve a user property's display name to its ident.
                if prop_name.startswith(":"):
                    ident = prop_name
                else:
                    ident = api.resolve_property_ident(prop_name)
                if not ident:
                    results.append(f"⚠️ Property '{prop_name}' not found")
                    continue

                api._upsert_block_property(block_uuid, ident, value)
                results.append(f"✅ {prop_name} = {value}")

            return [TextContent(
                type="text",
                text=f"Set properties on block {block_uuid}:\n" + "\n".join(results),
            )]

        except Exception as e:
            logger.error(f"Failed to set block properties: {str(e)}")
            return [TextContent(
                type="text",
                text=f"❌ Failed to set block properties: {str(e)}",
            )]


class SetBlockCollapsedToolHandler(ToolHandler):
    """Collapse or expand a block (its children are hidden when collapsed)."""

    access_policy = [
        access.BlockNamespace("block_uuid"),
        access.BlockTag("block_uuid"),
    ]

    def __init__(self):
        super().__init__("set_block_collapsed")

    def get_tool_description(self):
        return Tool(
            name=self.name,
            description="Collapse or expand an existing LogSeq block by UUID.",
            input_schema={
                "type": "object",
                "properties": {
                    "block_uuid": {
                        "type": "string",
                        "description": "UUID of the block to collapse/expand",
                    },
                    "collapsed": {
                        "type": "boolean",
                        "description": "true to collapse, false to expand (default true)",
                        "default": True,
                    },
                },
                "required": ["block_uuid"],
            },
        )

    def _run(self, api, args: dict) -> list[TextContent]:
        if "block_uuid" not in args:
            raise RuntimeError("block_uuid argument required")
        block_uuid = args["block_uuid"]
        collapsed = bool(args.get("collapsed", True))
        try:
            api.set_block_collapsed(block_uuid, collapsed)
            state = "collapsed" if collapsed else "expanded"
            return [TextContent(type="text", text=f"✅ Block '{block_uuid}' {state}")]
        except Exception as e:
            logger.error(f"Failed to set collapsed on block: {str(e)}")
            return [TextContent(
                type="text",
                text=f"❌ Failed to set collapsed on block '{block_uuid}': {str(e)}",
            )]


class InsertBlockTreeToolHandler(ToolHandler):
    """Insert a whole tree of blocks under (or after) an existing block in one call."""

    access_policy = [
        access.BlockNamespace("parent_block_uuid"),
        access.BlockTag("parent_block_uuid"),
    ]

    def __init__(self):
        super().__init__("insert_block_tree")

    def get_tool_description(self):
        return Tool(
            name=self.name,
            description="""Insert a tree of blocks, written as nested markdown, under or after an existing block in a single call.

Uses the same markdown parser as create_page/update_page (bullets, numbered lists,
headings, code blocks), so indentation becomes block nesting. Unlike update_page,
which can only append at the end of a page, this targets any existing block.

- sibling=false (default): the top-level blocks become the LAST children of parent_block_uuid
- sibling=true: the top-level blocks are inserted as siblings directly after parent_block_uuid

YAML frontmatter is not supported (there is no page to attach it to).

Example content:
- Candidate A
  - Status: Progress
  - Review notes
    - Strengths
      - Point one
- Candidate B""",
            input_schema={
                "type": "object",
                "properties": {
                    "parent_block_uuid": {
                        "type": "string",
                        "description": "UUID of the reference block. sibling=false inserts the tree as its children; sibling=true inserts the tree after it at the same level.",
                    },
                    "content": {
                        "type": "string",
                        "description": "Nested markdown describing the blocks to insert",
                    },
                    "sibling": {
                        "type": "boolean",
                        "description": "false (default) = insert as children of parent_block_uuid. true = insert as siblings after it.",
                        "default": False,
                    },
                },
                "required": ["parent_block_uuid", "content"],
            },
        )

    def _run(self, api, args: dict) -> list[TextContent]:
        if "parent_block_uuid" not in args or "content" not in args:
            raise RuntimeError("parent_block_uuid and content arguments required")

        parent_uuid = args["parent_block_uuid"]
        content = args["content"] or ""
        sibling = bool(args.get("sibling", False))

        if parser.FRONTMATTER_PATTERN.match(content):
            return [TextContent(
                type="text",
                text="❌ YAML frontmatter is not supported by insert_block_tree; use update_page for page properties",
            )]

        nodes = parser.parse_markdown_to_blocks(content)
        if not nodes:
            return [TextContent(type="text", text="❌ No blocks found in content")]

        blocks = parser.blocks_to_batch_format(nodes)
        total = _count_batch_blocks(blocks)

        try:
            result = api.insert_batch_block(parent_uuid, blocks, sibling=sibling)
        except Exception as e:
            logger.error(f"Failed to insert block tree: {str(e)}")
            return [TextContent(
                type="text",
                text=f"❌ Failed to insert block tree under '{parent_uuid}': {str(e)}",
            )]

        relationship = "siblings after" if sibling else "children of"
        lines = [
            f"✅ Inserted {total} block(s) ({len(blocks)} top-level) as {relationship} {parent_uuid}",
        ]
        created = result if isinstance(result, list) else []
        top_level = [b for b in created if isinstance(b, dict) and b.get("uuid")]
        if top_level:
            lines.append("Top-level block UUIDs:")
            for b in top_level[: len(blocks)]:
                preview = (b.get("content") or "").split("\n", 1)[0]
                if len(preview) > 60:
                    preview = preview[:60] + "..."
                lines.append(f"- {b['uuid']}  {preview}")
        return [TextContent(type="text", text="\n".join(lines))]


def _count_batch_blocks(blocks: list[dict]) -> int:
    """Count every block in an IBatchBlock tree."""
    return sum(1 + _count_batch_blocks(b.get("children") or []) for b in blocks)

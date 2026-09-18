"""Generate function-tool specs from the tools' Pydantic argument models."""

from copy import deepcopy

from app.services.chat.tools.chat_tool import ChatTool


def _inline_refs(node, defs: dict):
    """Replace `$ref`s with the definitions they point to. Enum fields arrive as refs, and a flat schema is the most
    widely accepted form for tool parameters."""
    if isinstance(node, list):
        return [_inline_refs(item, defs) for item in node]
    if not isinstance(node, dict):
        return node
    if "$ref" in node:
        resolved = deepcopy(defs[node["$ref"].rsplit("/", 1)[1]])
        resolved.update({k: v for k, v in node.items() if k != "$ref"})
        return _inline_refs(resolved, defs)
    # Pydantic's auto-generated "title" strings are noise to the model ("title" as a property *name* is kept)
    return {k: _inline_refs(v, defs) for k, v in node.items() if not (k == "title" and isinstance(v, str))}


def tool_spec(tool: ChatTool) -> dict:
    schema = tool.args_model.model_json_schema()
    parameters = _inline_refs({k: v for k, v in schema.items() if k != "$defs"}, schema.get("$defs", {}))
    parameters.pop("description", None)  # the args model's docstring is for developers; the tool has its own
    parameters.setdefault("properties", {})
    return {
        "type": "function",
        "function": {"name": tool.name, "description": tool.description, "parameters": parameters},
    }


def tool_specs(tools: list[ChatTool]) -> list[dict]:
    return [tool_spec(tool) for tool in tools]

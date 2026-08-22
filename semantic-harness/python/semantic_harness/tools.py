"""Tool protocol — JSON-schema generation and registry for LLM function calling."""
from __future__ import annotations

import inspect
import json
import types
from collections.abc import Callable
from typing import (
    Any,
    Union,
    get_args,
    get_origin,
    get_type_hints,
)

_TYPE_MAP: dict[type, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
}


def _annotation_to_schema(annotation: Any) -> dict[str, Any]:
    """Map a Python type annotation to a JSON-schema fragment."""
    if annotation is inspect.Parameter.empty or annotation is type(None):
        return {}

    origin = get_origin(annotation)
    if origin is Union or isinstance(annotation, types.UnionType):
        fragments = [
            s
            for s in (_annotation_to_schema(a) for a in get_args(annotation))
            if s
        ]
        if len(fragments) == 1:
            return fragments[0]
        if fragments:
            return {"anyOf": fragments}
        return {}
    if origin in (list, list):
        args = get_args(annotation)
        items = _annotation_to_schema(args[0]) if args else {}
        return {"type": "array", **({"items": items} if items else {})}
    if origin in (dict, dict):
        return {"type": "object"}
    if annotation in _TYPE_MAP:
        return {"type": _TYPE_MAP[annotation]}
    return {}


def function_to_schema(fn: Callable) -> dict[str, Any]:
    """
    Generate an OpenAI-style tool schema from a function's type hints and docstring.

    The first paragraph of the docstring becomes the description. Parameters
    without defaults are marked required.
    """
    signature = inspect.signature(fn)
    try:
        hints = get_type_hints(fn)
    except Exception:
        hints = {}

    properties: dict[str, Any] = {}
    required: list[str] = []

    for param_name, param in signature.parameters.items():
        if param_name in ("self", "cls"):
            continue
        if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
            continue

        annotation = hints.get(param_name, param.annotation)
        prop = _annotation_to_schema(annotation)

        has_default = param.default is not inspect.Parameter.empty
        if not has_default:
            required.append(param_name)
        elif param.default is not None and prop:
            prop = {**prop, "default": param.default}

        properties[param_name] = prop

    doc = inspect.getdoc(fn) or ""
    description = doc.split("\n\n")[0].strip()

    return {
        "type": "function",
        "function": {
            "name": getattr(fn, "__name__", str(fn)),
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


def tool(fn: Callable | None = None, *, name: str | None = None):
    """
    Mark a function as a tool.

    Can be used bare (@tool) or with a custom name (@tool(name="search_web").
    Registration still happens via ToolRegistry.register / register_object.
    """

    def decorate(f: Callable) -> Callable:
        f._is_tool = True  # type: ignore[attr-defined]
        if name:
            f._tool_name = name  # type: ignore[attr-defined]
        return f

    return decorate(fn) if fn is not None else decorate


class ToolRegistry:
    """Registry of LLM-callable tools with automatic schema generation."""

    def __init__(self):
        self._tools: dict[str, Callable] = {}

    def register(self, fn: Callable, *, name: str | None = None) -> Callable:
        """Register a callable as a tool."""
        key = (
            name
            or getattr(fn, "_tool_name", None)
            or getattr(fn, "__name__", None)
        )
        if not key:
            raise ValueError("Cannot register a tool without a name")
        self._tools[key] = fn
        return fn

    def register_object(
        self,
        obj: Any,
        *,
        skip: tuple = ("run", "arun"),
    ) -> list[str]:
        """
        Register all public, documented methods of an object (class-as-agent).

        Methods starting with "_" and names in `skip` are excluded. Returns
        the list of registered tool names.
        """
        registered: list[str] = []
        for attr_name in dir(obj):
            if attr_name.startswith("_") or attr_name in skip:
                continue
            attr = getattr(obj, attr_name)
            if callable(attr) and inspect.getdoc(attr):
                self.register(attr)
                registered.append(attr_name)
        return registered

    def schemas(self) -> list[dict[str, Any]]:
        """OpenAI-compatible tool schemas for all registered tools."""
        return [function_to_schema(fn) for fn in self._tools.values()]

    def names(self) -> list[str]:
        return list(self._tools.keys())

    def execute(self, name: str, arguments: str | dict[str, Any]) -> str:
        """
        Execute a tool by name. Never raises — failures come back as
        "Error: ..." strings the LLM can read and react to.
        """
        if name not in self._tools:
            return f"Error: unknown tool '{name}'. Available: {self.names()}"

        if isinstance(arguments, str):
            try:
                args = json.loads(arguments) if arguments.strip() else {}
            except json.JSONDecodeError as e:
                return f"Error: invalid JSON arguments for '{name}': {e}"
        else:
            args = arguments

        if not isinstance(args, dict):
            return f"Error: arguments for '{name}' must decode to an object"

        try:
            result = self._tools[name](**args)
        except TypeError as e:
            return f"Error: bad arguments for '{name}': {e}"
        except Exception as e:
            return f"Error executing '{name}': {e}"

        if isinstance(result, str):
            return result
        try:
            return json.dumps(result, default=str)
        except (TypeError, ValueError):
            return str(result)

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools

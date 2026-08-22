"""Sandboxed Python REPL for executing LLM-written code (CodeAct strategy).

Security note: this is a best-effort in-process sandbox. It restricts the
builtin namespace and captures `print()` output, but it cannot guarantee full
isolation from the host process (a determined escape via reflection is
possible). Run untrusted workloads in a container/subprocess for hard
isolation. A timed-out execution abandons its thread — the REPL namespace
should be considered corrupted afterwards; create a fresh PythonREPL.
"""
from __future__ import annotations

import ast
import builtins as _builtin_mod
import io
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor  # noqa: F401 (re-export convenience)
from dataclasses import dataclass
from typing import Any

_REAL_PRINT = _builtin_mod.print

_SAFE_BUILTINS: dict[str, Any] = {
    "abs": abs, "all": all, "any": any, "ascii": ascii, "bin": bin,
    "bool": bool, "bytes": bytes, "callable": callable, "chr": chr,
    "complex": complex, "dict": dict, "divmod": divmod, "enumerate": enumerate,
    "filter": filter, "float": float, "format": format, "frozenset": frozenset,
    "hasattr": hasattr, "hash": hash, "hex": hex, "int": int,
    "isinstance": isinstance, "issubclass": issubclass, "iter": iter, "len": len,
    "list": list, "map": map, "max": max, "min": min, "next": next,
    "oct": oct, "ord": ord, "pow": pow, "range": range, "repr": repr,
    "reversed": reversed, "round": round, "set": set, "slice": slice,
    "sorted": sorted, "str": str, "sum": sum, "tuple": tuple, "type": type,
    "zip": zip,
    # Common exceptions so LLM-written code can raise/catch normally
    "ArithmeticError": ArithmeticError, "AssertionError": AssertionError,
    "AttributeError": AttributeError, "Exception": Exception,
    "IndexError": IndexError, "KeyError": KeyError, "LookupError": LookupError,
    "NameError": NameError, "RuntimeError": RuntimeError, "StopIteration": StopIteration,
    "TypeError": TypeError, "ValueError": ValueError, "ZeroDivisionError": ZeroDivisionError,
}


@dataclass
class ExecutionResult:
    """Outcome of one REPL execution."""
    success: bool
    output: str = ""
    error: str = ""
    value: Any = None


class PythonREPL:
    """
    A persistent, restricted Python namespace.

    The same globals dict survives across execute() calls, so variables
    defined in one step are visible in the next — exactly what CodeAct loops
    need. Pass `locals` to expose agent state / tools to generated code.

    Output capture is thread-safe: we never touch process-global sys.stdout.
    Instead, the sandbox gets its own `print` bound to a per-run buffer.
    """

    def __init__(
        self,
        locals: dict[str, Any] | None = None,
        *,
        restrict_builtins: bool = True,
        default_timeout: float = 10.0,
    ):
        self._globals: dict[str, Any] = {"__name__": "__repl__"}
        if restrict_builtins:
            sandbox_builtins = dict(_SAFE_BUILTINS)
        else:
            sandbox_builtins = {n: getattr(_builtin_mod, n) for n in dir(_builtin_mod)}
        # Sandbox-local print: writes to the active run buffer, never to sys.stdout
        sandbox_builtins["print"] = self._capture_print
        self._globals["__builtins__"] = sandbox_builtins
        if locals:
            self._globals.update(locals)

        self.default_timeout = default_timeout
        self._active_buffer: io.StringIO | None = None

    def _capture_print(self, *args: Any, sep: str = " ", end: str = "\n", **_: Any) -> None:
        buf = self._active_buffer
        text = sep.join(str(arg) for arg in args) + end
        if buf is not None:
            buf.write(text)
        else:
            _REAL_PRINT(text, end="")

    def execute(self, code: str, timeout: float | None = None) -> ExecutionResult:
        """
        Execute a block of code. Returns stdout (captured from `print`), the
        value of a trailing bare expression (if any), and error text on failure.
        """
        timeout = timeout or self.default_timeout
        result: dict[str, ExecutionResult] = {}

        worker = threading.Thread(
            target=self._run_code, args=(code, result), daemon=True
        )
        worker.start()
        worker.join(timeout)

        if worker.is_alive():
            return ExecutionResult(
                success=False,
                error=f"Execution timed out after {timeout}s "
                      f"(thread abandoned; namespace may be corrupted)",
            )
        return result.get("res", ExecutionResult(success=False, error="no result"))

    def _run_code(self, code: str, out: dict[str, ExecutionResult]):
        buf = io.StringIO()
        previous_buffer = self._active_buffer
        self._active_buffer = buf
        try:
            tree = ast.parse(code)
            value = None
            # Capture a trailing bare expression like an interactive REPL
            last = tree.body[-1] if tree.body else None
            if isinstance(last, ast.Expr):
                prefix = tree.body[:-1]
                if prefix:
                    exec(
                        compile(ast.Module(body=prefix, type_ignores=[]), "<repl>", "exec"),
                        self._globals,
                    )
                value = eval(compile(ast.Expression(last.value), "<repl>", "eval"), self._globals)
            else:
                exec(compile(tree, "<repl>", "exec"), self._globals)

            out["res"] = ExecutionResult(success=True, output=buf.getvalue(), value=value)
        except Exception:
            out["res"] = ExecutionResult(
                success=False,
                output=buf.getvalue(),
                error=traceback.format_exc(limit=3),
            )
        finally:
            self._active_buffer = previous_buffer

    def get(self, name: str, default: Any = None) -> Any:
        return self._globals.get(name, default)

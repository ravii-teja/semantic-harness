from __future__ import annotations
import ast
import io
import time
import traceback
import threading
import queue
import builtins
from contextlib import redirect_stdout, redirect_stderr
from dataclasses import dataclass
from typing import Any

# Default safe allowed builtins
_SAFE_BUILTINS = {
    name: getattr(builtins, name)
    for name in [
        "abs", "all", "any", "ascii", "bin", "bool", "bytearray", "bytes",
        "chr", "complex", "dict", "dir", "divmod", "enumerate", "filter",
        "float", "format", "frozenset", "getattr", "hasattr", "hash", "hex",
        "id", "int", "isinstance", "issubclass", "iter", "len", "list",
        "map", "max", "min", "next", "oct", "ord", "pow", "print", "range",
        "repr", "reversed", "round", "set", "slice", "sorted", "str", "sum",
        "tuple", "type", "vars", "zip",
        "ArithmeticError", "AssertionError", "AttributeError", "BaseException",
        "BufferError", "BytesWarning", "DeprecationWarning", "EOFError",
        "Exception", "FloatingPointError", "FutureWarning", "GeneratorExit",
        "ImportError", "ImportWarning", "IndexError", "KeyError",
        "KeyboardInterrupt", "LookupError", "MemoryError", "NameError",
        "NotImplementedError", "OSError", "OverflowError", "PendingDeprecationWarning",
        "ReferenceError", "RuntimeError", "RuntimeWarning", "StopIteration",
        "SyntaxError", "SyntaxWarning", "SystemError", "SystemExit",
        "TabError", "TypeError", "UnboundLocalError", "UnicodeDecodeError",
        "UnicodeEncodeError", "UnicodeError", "UnicodeTranslateError",
        "UnicodeWarning", "UserWarning", "ValueError", "Warning", "ZeroDivisionError",
        "True", "False", "None",
    ]
    if hasattr(builtins, name)
}


@dataclass
class REPLResult:
    code: str
    output: str
    error: str | None
    return_value: Any
    execution_time_ms: float
    success: bool

    @property
    def value(self) -> Any:
        return self.return_value


# Alias for backward compatibility
ExecutionResult = REPLResult


class PythonREPL:
    """
    Stateful, sandboxed Python REPL for CodeAct agent execution.

    Security & execution model:
    - AST-level import checking against allowed whitelist
    - Restricted builtins in sandbox mode
    - Timeout-protected execution
    - Return value capture for expressions
    """

    ALLOWED_IMPORTS = {
        "json", "math", "re", "datetime", "collections",
        "itertools", "functools", "typing", "dataclasses",
        "decimal", "fractions", "statistics", "random",
        "string", "textwrap", "unicodedata", "hashlib",
        "base64", "urllib.parse",
    }

    def __init__(
        self,
        locals: dict[str, Any] | None = None,
        default_timeout: float = 5.0,
        timeout: float | None = None,
        restrict_builtins: bool = True,
        sandbox: bool | None = None,
        allowed_imports: set[str] | None = None,
    ):
        self.default_timeout = timeout if timeout is not None else default_timeout
        self.restrict_builtins = sandbox if sandbox is not None else restrict_builtins
        self.allowed_imports = allowed_imports or self.ALLOWED_IMPORTS
        self._namespace: dict[str, Any] = {}
        if self.restrict_builtins:
            self._namespace["__builtins__"] = dict(_SAFE_BUILTINS)
        else:
            self._namespace["__builtins__"] = builtins

        if locals:
            self._namespace.update(locals)
        self._history: list[REPLResult] = []

    def _check_ast(self, code: str) -> str | None:
        """Returns error string if code contains blocked constructs."""
        if not self.restrict_builtins:
            return None
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return f"SyntaxError: {e}"

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    if root not in self.allowed_imports:
                        return f"SecurityError: import '{alias.name}' is not allowed in sandbox mode. Allowed: {sorted(self.allowed_imports)}"
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                root = module.split(".")[0]
                if root not in self.allowed_imports:
                    return f"SecurityError: 'from {module} import ...' is not allowed in sandbox mode."
        return None

    def execute(self, code: str, timeout: float | None = None) -> REPLResult:
        """Execute code in the stateful namespace with timeout protection."""
        # AST check
        if self.restrict_builtins:
            err = self._check_ast(code)
            if err:
                result = REPLResult(
                    code=code,
                    output="",
                    error=err,
                    return_value=None,
                    execution_time_ms=0.0,
                    success=False,
                )
                self._history.append(result)
                return result

        timeout_val = timeout or self.default_timeout
        q: queue.Queue[tuple[str, str | None, Any, float, bool]] = queue.Queue()

        def _worker():
            stdout_buf = io.StringIO()
            stderr_buf = io.StringIO()
            return_val = None
            error_str = None
            t_start = time.perf_counter()

            try:
                with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
                    try:
                        # Try eval (expression mode to capture value)
                        compiled = compile(code, "<repl>", "eval")
                        return_val = eval(compiled, self._namespace)
                    except SyntaxError:
                        # Fall back to exec
                        compiled = compile(code, "<repl>", "exec")
                        exec(compiled, self._namespace)
            except Exception:
                error_str = traceback.format_exc()

            t_elapsed = (time.perf_counter() - t_start) * 1000
            out_str = stdout_buf.getvalue()
            if stderr_buf.getvalue():
                out_str += stderr_buf.getvalue()

            q.put((out_str, error_str, return_val, t_elapsed, error_str is None))

        th = threading.Thread(target=_worker, daemon=True)
        th.start()
        th.join(timeout_val)

        if th.is_alive():
            result = REPLResult(
                code=code,
                output="",
                error=f"Execution timed out after {timeout_val:.1f}s",
                return_value=None,
                execution_time_ms=timeout_val * 1000,
                success=False,
            )
        else:
            out_str, error_str, return_val, t_elapsed, is_success = q.get()
            result = REPLResult(
                code=code,
                output=out_str,
                error=error_str,
                return_value=return_val,
                execution_time_ms=t_elapsed,
                success=is_success,
            )

        self._history.append(result)
        return result

    def reset(self) -> None:
        """Clear namespace and history."""
        self._namespace = {}
        if self.restrict_builtins:
            self._namespace["__builtins__"] = dict(_SAFE_BUILTINS)
        else:
            self._namespace["__builtins__"] = builtins
        self._history = []

    @property
    def history(self) -> list[REPLResult]:
        return list(self._history)

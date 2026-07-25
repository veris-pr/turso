"""registry — name/arity → descriptor; scalar vs aggregate; deterministic flag.

Ports: core/function.rs (``FunctionFlags``, function dispatch table).
Phase: 6
Status: IMPLEMENTED (scalar function registry + initial function set).

The registry maps case-insensitive function names to Python callables. Each
function takes a list of :class:`pyturso.types.value.Value` arguments and
returns a single :class:`Value`. Variadic functions (like ``coalesce``,
``min``, ``max``) accept any number of arguments; fixed-arity functions
validate their arg count.

The registry is populated at import time with the initial scalar function set
(Phase 6 batch). Aggregate functions arrive in Phase 10.
"""

from __future__ import annotations

from typing import Callable

from pyturso.types.value import Value

__all__ = ["FunctionRegistry", "ScalarFunc", "registry", "call_function"]

#: A scalar function: takes a list of Values, returns a Value.
ScalarFunc = Callable[[list[Value]], Value]


class FunctionRegistry:
    """Case-insensitive name → function descriptor.

    Functions are keyed by uppercased name. Arity is checked at call time
    (variadic functions use ``arity = -1``).
    """

    def __init__(self) -> None:
        self._funcs: dict[str, tuple[int, ScalarFunc]] = {}

    def register(self, name: str, arity: int, func: ScalarFunc) -> None:
        """Register a function. ``arity = -1`` means variadic."""
        self._funcs[name.upper()] = (arity, func)

    def get(self, name: str, n_args: int) -> ScalarFunc | None:
        """Look up a function by name and argument count.

        Returns the callable, or ``None`` if not found. For variadic functions
        (arity = -1), any argument count is accepted.
        """
        entry = self._funcs.get(name.upper())
        if entry is None:
            return None
        arity, func = entry
        if arity >= 0 and arity != n_args:
            return None
        return func

    def has(self, name: str) -> bool:
        return name.upper() in self._funcs


#: The global function registry (populated at import time).
registry: FunctionRegistry = FunctionRegistry()


def call_function(name: str, args: list[Value]) -> Value:
    """Call a registered function by name.

    Raises ``ValueError`` if the function is not found or arity mismatches.
    """
    func = registry.get(name, len(args))
    if func is None:
        raise ValueError(f"no such function: {name}({len(args)} args)")
    return func(args)


# --- register the initial scalar function set ---
from . import scalar  # noqa: E402,F401
from . import datetime  # noqa: E402,F401
from . import printf  # noqa: E402,F401
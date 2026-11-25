"""RDP-S04 conceptual composition, not a replacement sovereign scanner."""

from __future__ import annotations

from functools import wraps
from collections.abc import Callable
from .contracts import Call, Result


def guard(
    name: str, prerequisite: tuple[str, ...], predicate: Callable[[Call], bool]
) -> Callable[[Callable[[Call], Result]], Callable[[Call], Result]]:
    def decorate(target: Callable[[Call], Result]) -> Callable[[Call], Result]:
        @wraps(target)
        def wrapped(call: Call) -> Result:
            if call.stages != prerequisite:
                raise ValueError("DENY_GUARD_ORDER")
            if not predicate(call):
                raise ValueError("DENY_" + name.upper())
            admitted = call.model_copy(update={"stages": (*call.stages, name)})
            return target(admitted)

        return wrapped

    return decorate


scanner = guard("scanner", (), lambda call: call.authorized)
semantic = guard("semantic", ("scanner",), lambda call: call.semantic_label == "READ")
watchdog = guard("watchdog", ("scanner", "semantic"), lambda call: call.source_intact)


@scanner
@semantic
@watchdog
def read_reference(call: Call) -> Result:
    if call.stages != ("scanner", "semantic", "watchdog"):
        raise ValueError("DENY_TARGET_ENTRY")
    return Result(stages=(*call.stages, "target"), result="reference-read")

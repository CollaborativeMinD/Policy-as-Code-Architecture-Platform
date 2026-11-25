"""RDP-B05 fixed public skeleton with a pure normalization extension point."""

from __future__ import annotations

from .contracts import Request, Result


class Pipeline:
    def __init_subclass__(cls) -> None:
        super().__init_subclass__()
        if "run" in cls.__dict__:
            raise TypeError("DENY_SKELETON_OVERRIDE")

    def normalize(self, text: str) -> str:
        return text.strip()

    def run(self, request: Request) -> Result:
        parsed = self.normalize(request.text)
        validated = Request(text=parsed)
        return Result(value=validated.text, steps=("parse", "validate", "emit"))


class UppercasePipeline(Pipeline):
    def normalize(self, text: str) -> str:
        return text.strip().upper()

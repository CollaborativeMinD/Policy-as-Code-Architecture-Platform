"""Live worked and negative witnesses; bounded local fixture effects only."""

from __future__ import annotations

from pydantic import ValidationError
from .contracts import External
from .reference import TemperatureAdapter


def run_example(case: str = "nominal") -> dict[str, object]:
    temperature = 25000 if case == "nominal" else -273150
    raw = External(version="1", unit="mC", temperature=temperature)
    adapter = TemperatureAdapter()
    value = adapter.convert(raw)
    try:
        External(version="2", unit="F", temperature=temperature)
    except ValidationError:
        denied = True
    wrong = temperature
    return {
        "inputs": raw.model_dump(),
        "computed": value.model_dump(),
        "positive_check": adapter.inverse(value) == raw
        and value.temperature == temperature + 273150,
        "negative_detected": denied and wrong != value.temperature,
        "negative_hypothesis": (
            "Renaming a Celsius field without unit conversion corrupts the contract."
        ),
    }

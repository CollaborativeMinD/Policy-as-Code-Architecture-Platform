import marimo

__generated_with = "0.25.1"
app = marimo.App(width="medium", app_title="Proxy — HMT pattern book")


@app.cell
def _():
    import hashlib
    import inspect
    import json
    import time
    from pydantic import ValidationError
    import marimo as mo
    from hmt_rdp.pattern_loader import leaf, load

    book_leaf = leaf("proxy")
    implementation = load("proxy", "reference")
    contracts = load("proxy", "contracts")
    example = load("proxy", "example")
    lesson = json.loads((book_leaf / "lesson.json").read_text())
    return (
        book_leaf,
        contracts,
        example,
        hashlib,
        implementation,
        inspect,
        json,
        lesson,
        mo,
        time,
        ValidationError,
    )


@app.cell
def _(example, inspect, lesson, mo):
    mo.vstack(
        [
            mo.md(lesson["bluf"] + lesson["identity"] + lesson["problem"]),
            mo.md(
                "**Bounded educational pressure fixture.** Actual executed code. "
                "No operational authority."
            ),
            mo.md("```python\n" + inspect.getsource(example) + "\n```"),
            mo.md(lesson["mechanism"]),
        ]
    )


@app.cell
def _(hashlib, implementation, inspect, mo):
    executed_source = inspect.getsource(implementation)
    source_hash = hashlib.sha256(executed_source.encode()).hexdigest()
    mo.vstack(
        [
            mo.md(
                "## 5. Canonical working implementation\nActual executed source; SHA-256: `"
                + source_hash
                + "`"
            ),
            mo.md("```python\n" + executed_source + "\n```"),
        ]
    )
    return (source_hash,)


@app.cell
def _(contracts, lesson, mo):
    case = mo.ui.dropdown(["nominal", "edge"], value="nominal", label="Worked input")
    mo.vstack(
        [
            mo.md(lesson["inputs"]),
            case,
            mo.json(
                {
                    "invalid_input": lesson["invalid_payload"],
                    "exact_contract_bounds": getattr(
                        contracts, lesson["invalid_model"]
                    ).model_json_schema(),
                }
            ),
        ]
    )
    return (case,)


@app.cell
def _(case, example, source_hash, time):
    started = time.perf_counter()
    computed_example = example.run_example(case.value)
    witness = {
        "source_sha256": source_hash,
        "elapsed_ms": (time.perf_counter() - started) * 1000,
        **computed_example,
    }
    return (witness,)


@app.cell
def _(contracts, json, lesson, ValidationError):
    invalid_denied = False
    try:
        getattr(contracts, lesson["invalid_model"]).model_validate_json(
            json.dumps(lesson["invalid_payload"])
        )
    except ValidationError:
        invalid_denied = True
    return (invalid_denied,)


@app.cell
def _(invalid_denied, lesson, mo, witness):
    mo.vstack(
        [
            mo.md("## 7. Executed witness\nRecomputed from the current input and implementation."),
            mo.ui.table(
                [
                    {
                        "predicate": "positive oracle",
                        "actual": witness["positive_check"],
                        "expected": True,
                    },
                    {
                        "predicate": "negative hypothesis falsified",
                        "actual": witness["negative_detected"],
                        "expected": True,
                    },
                    {
                        "predicate": "invalid input rejected",
                        "actual": invalid_denied,
                        "expected": True,
                    },
                ],
                selection=None,
            ),
            mo.json(
                {
                    "invalid_input": lesson["invalid_payload"],
                    "invalid_denied": invalid_denied,
                    **witness,
                }
            ),
        ]
    )


@app.cell
def _(book_leaf, json, lesson, mo, witness):
    mo.vstack(
        [
            mo.md(lesson["pressure"]),
            mo.json(
                {
                    "positive_check": witness["positive_check"],
                    "negative_detected": witness["negative_detected"],
                }
            ),
            mo.md(lesson["applicability"] + lesson["reproducibility"]),
            mo.json(
                {
                    "source_test_evidence_pins": json.loads(
                        (book_leaf / "manifest.json").read_text()
                    ),
                    "qualification": json.loads(
                        (book_leaf / "evidence/qualification.json").read_text()
                    ),
                }
            ),
        ]
    )


if __name__ == "__main__":
    app.run()

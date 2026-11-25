"""Typed adapters for the original behavioral, creational and structural leaves."""

from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

from policy_runtime.contracts import boolean, choice, integer, model, require, settings


def strategy(c, r, v):
    request = model(c.Request, v, "algorithm", "costs")
    return r.select(request).model_dump(mode="json")


def observer(c, r, v):
    settings(v, "event", "subscribers")
    event = model(c.Event, v["event"], "event_id", "sequence", "payload")
    require(type(v["subscribers"]) is list and 1 <= len(v["subscribers"]) <= 2, "SUBSCRIBER_BOUND")
    ports = {"echo": lambda e: e.payload, "uppercase": lambda e: e.payload.upper()}
    publisher = r.Publisher(tuple(ports[choice(name, *ports)] for name in v["subscribers"]))
    result = publisher.publish(event)
    require(publisher.publish(event).status == "DUPLICATE", "OBSERVER_REPLAY_DRIFT")
    return result.model_dump(mode="json")


def state(c, r, v):
    tick = model(c.Tick, v, "state", "soft_failures", "recovery_streak", "pressure",
                 "hard_terminal", "emergency", "history_epoch")
    return r.transition(tick).model_dump(mode="json")


def command(c, r, v):
    settings(v, "operation_id", "value", "mode")
    operation = model(c.Operation, v | {"authority": "fixture:effect"}, "operation_id", "value", "mode", "authority")
    with TemporaryDirectory() as folder:
        store = r.CommandStore(Path(folder) / "fixture.sqlite")
        if operation.mode == "COMMIT_CONFINED_TEST":
            try:
                store.execute(operation, fault="after_effect")
            except RuntimeError as error:
                require(str(error) == "INJECTED_BEFORE_COMMIT" and store.counts() == (0, 0), "ROLLBACK_DRIFT")
            else:
                raise ValueError("FAULT_DID_NOT_BLOCK_COMMIT")
        receipt = store.execute(operation)
        expected = 1 if operation.mode == "COMMIT_CONFINED_TEST" else 0
        require(store.execute(operation) == receipt and store.counts() == (expected, expected), "COMMAND_REPLAY_DRIFT")
        return receipt.model_dump(mode="json")


def template(c, r, v):
    settings(v, "normalizer", "text")
    normalizers = {"strip": r.Pipeline, "uppercase": r.UppercasePipeline}
    selected = normalizers[choice(v["normalizer"], *normalizers)]()
    return selected.run(model(c.Request, {"text": v["text"]}, "text")).model_dump(mode="json")


def iterator(c, r, v):
    settings(v, "records", "size", "offset", "now", "expires_at")
    require(type(v["records"]) is list and 1 <= len(v["records"]) <= 32, "RECORD_BOUND")
    store = r.EvidenceIterator(tuple(model(c.Record, item, "record_id", "value") for item in v["records"]))
    cursor = c.Cursor(offset=integer(v["offset"], 0, 32), snapshot_digest=store.snapshot_digest,
                      expires_at=integer(v["expires_at"], 1, 2**63 - 1))
    return store.page(cursor, integer(v["size"], 1, 4), integer(v["now"], 0, 2**63 - 1)).model_dump(mode="json")


def chain(c, r, v):
    settings(v, "guards")
    require(type(v["guards"]) is list, "GUARD_LIST_REQUIRED")
    chain = r.GuardChain(tuple(v["guards"]))
    claims = dict.fromkeys(r.FIELDS, True)
    allowed = chain.check(c.Context(**claims))
    denied = chain.check(c.Context(**(claims | {"authenticated": False})))
    require(allowed.disposition == "READ_ADMITTED" and denied.disposition == "DENY"
            and denied.visited == ("authenticate",), "CHAIN_GUARD_DRIFT")
    return {"admitted": allowed.model_dump(mode="json"), "denied": denied.model_dump(mode="json")}


def singleton(c, r, v):
    config = model(c.Config, v, "tenant", "limit")
    scope = r.ScopedSingleton()
    try:
        first = scope.get(config)
        require(scope.get(config) is first, "SCOPE_IDENTITY_DRIFT")
        return first.model_dump(mode="json")
    finally:
        scope.close()


def builder(c, r, v):
    config = model(c.Config, v, "owner", "limit", "enabled")
    return r.Builder(config.owner).with_limit(config.limit).finish(config.enabled).model_dump(mode="json")


def factory_method(c, r, v):
    return r.create(model(c.Request, v, "provider", "text")).model_dump(mode="json")


def adapter(c, r, v):
    original = model(c.External, v, "version", "unit", "temperature")
    converter = r.TemperatureAdapter()
    converted = converter.convert(original)
    require(converter.inverse(converted) == original, "UNIT_ROUND_TRIP_DRIFT")
    return converted.model_dump(mode="json")


def facade(c, r, v):
    settings(v, "catalog_count", "evidence_count")
    catalog = c.Reading(subsystem="catalog", count=integer(v["catalog_count"], 0, 32))
    evidence = c.Reading(subsystem="evidence", count=integer(v["evidence_count"], 0, 32))
    return r.AuditFacade(lambda: catalog, lambda: evidence).inspect().model_dump(mode="json")


def proxy(c, r, v):
    settings(v, "now", "expires_at", "policy_epoch")
    content = Path(r.__file__).read_bytes()
    source_pin = sha256(content).hexdigest()
    capability = c.Capability(subject="reviewer", audience="pattern-reference", scope="read", resource="reference.py",
                              policy_epoch=integer(v["policy_epoch"], 1, 1),
                              expires_at=integer(v["expires_at"], 1, 2**63 - 1), source_digest=source_pin)
    result = r.ReferenceProxy(lambda: content).read(capability, integer(v["now"], 0, 2**63 - 1))
    return {"sha256": sha256(result).hexdigest(), "bytes": len(result)}


def decorator(c, r, v):
    settings(v, "guards", "semantic_label")
    require(v["guards"] == ["scanner", "semantic", "watchdog"], "DENY_GUARD_ORDER")
    label = choice(v["semantic_label"], "READ")
    verdict = r.read_reference(c.Call(authorized=True, semantic_label=label, source_intact=True))
    try:
        r.read_reference(c.Call(authorized=False, semantic_label=label, source_intact=True))
    except ValueError as error:
        require(str(error) == "DENY_SCANNER", "DECORATOR_GUARD_DRIFT")
    else:
        raise ValueError("DECORATOR_BYPASS")
    return verdict.model_dump(mode="json")


def composite(c, r, v):
    return {"weight": r.Composite().aggregate(model(c.Graph, v, "root", "nodes"))}


OPERATIONS = {
    "RDP-B01": strategy, "RDP-B02": observer, "RDP-B03": state, "RDP-B04": command,
    "RDP-B05": template, "RDP-B06": iterator, "RDP-B07": chain,
    "RDP-C01": singleton, "RDP-C02": builder, "RDP-C03": factory_method,
    "RDP-S01": adapter, "RDP-S02": facade, "RDP-S03": proxy, "RDP-S04": decorator, "RDP-S05": composite,
}

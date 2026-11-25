"""Require an explicitly reviewed bound and executed witness for every observed loop."""


def bind_power10(observed, contract, executions, analyzer):
    evidence = {row["id"]: row for row in executions}
    sites = {(row["path"], row["ast_digest"]): row for row in contract["bound_sites"]}
    measured = {(row["path"], row["ast_digest"]) for row in observed if "ast_digest" in row}
    if measured != set(sites):
        raise ValueError("POWER10_SITE_INVENTORY_CHANGED")
    for site in sites.values():
        witness = evidence.get(site["test_id"])
        if not site["bound"] or not witness or witness["passed"] is not True:
            raise ValueError("POWER10_BOUND_NOT_WITNESSED:" + site["path"])
    obligations = {}
    for rule, row in contract["rules"].items():
        witness = (
            analyzer if row["test_id"] == "POWER10:ANALYZERS" else evidence.get(row["test_id"])
        )
        if not witness or witness["passed"] is not True:
            raise ValueError("POWER10_RULE_NOT_WITNESSED:" + rule)
        obligations[rule] = {
            "execution_id": witness["id"],
            "platform_mapping": row["mapping"],
            "bound_sites": [
                site["ast_digest"]
                for site in observed
                if site["rule"] == rule and "ast_digest" in site
            ],
        }
    return {
        "observations": observed,
        "obligations": obligations,
        "executions": [*executions, analyzer],
    }

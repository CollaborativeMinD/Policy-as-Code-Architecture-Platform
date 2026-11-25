"""SQL schema compatible with native V&V table exports; SQLite is the local ledger."""

DDL = (
    "CREATE TABLE dimensions(kind TEXT,id TEXT,requirement TEXT NOT NULL,PRIMARY KEY(kind,id))",
    "CREATE TABLE predicates(id TEXT PRIMARY KEY,invariant_id TEXT,failure_id TEXT,"
    "gate_id TEXT,reason TEXT NOT NULL)",
    "CREATE TABLE candidates(id INTEGER PRIMARY KEY,invariant_id TEXT,failure_id TEXT,"
    "gate_id TEXT,status TEXT CHECK(status IN ('PENDING','NOT_APPLICABLE')),"
    "predicate_id TEXT REFERENCES predicates(id))",
    "CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL)",
    "CREATE TABLE assertions(id TEXT PRIMARY KEY,candidate_id INTEGER REFERENCES candidates(id),"
    "requirement TEXT,family TEXT,test_id TEXT,expected TEXT)",
    "CREATE TABLE executions(id TEXT PRIMARY KEY,assertion_id TEXT REFERENCES assertions(id),"
    "source_digest TEXT,outcome TEXT,actual TEXT,evidence_digest TEXT)",
    "CREATE TABLE supersessions(old_id TEXT,new_id TEXT,causal_summary TEXT,contract_change TEXT)",
    "CREATE TABLE causal_edges(id TEXT PRIMARY KEY,requirement TEXT)",
    "CREATE TABLE causal_witnesses(edge_id TEXT,experiment TEXT,execution_id TEXT,"
    "PRIMARY KEY(edge_id,experiment))",
    "CREATE TABLE case_bindings(candidate_id INTEGER PRIMARY KEY REFERENCES candidates(id),"
    "case_id TEXT UNIQUE,assertion_text TEXT NOT NULL)",
)

CROSS_JOIN = (
    "SELECT i.id,f.id,g.id FROM dimensions i CROSS JOIN dimensions f "
    "CROSS JOIN dimensions g WHERE i.kind='invariant' AND f.kind='failure' "
    "AND g.kind='gate' ORDER BY i.id,f.id,g.id"
)

TABLES = (
    "dimensions",
    "predicates",
    "candidates",
    "metadata",
    "assertions",
    "executions",
    "supersessions",
    "causal_edges",
    "causal_witnesses",
    "case_bindings",
)


def create_tables(db):
    db.execute("PRAGMA foreign_keys=ON")
    for statement in DDL:
        db.execute(statement)


def protect_history(db):
    for table in TABLES:
        for operation in ("UPDATE", "DELETE"):
            db.execute(
                f"CREATE TRIGGER freeze_{table}_{operation} BEFORE {operation} "
                f"ON {table} BEGIN SELECT RAISE(ABORT,'APPEND_ONLY_LEDGER'); END"
            )

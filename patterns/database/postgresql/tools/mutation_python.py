"""Eight executable Python/Lua semantic mutants with focused public witnesses."""

from .mutation_models import Mutation, Patch

SOURCE = "src/hmt_pg_patterns/"
SCANNER = SOURCE + "streaming_scan.py"
SCANNER_TESTS = "tests/test_streaming_scanner.py::"

MUTATIONS = (
    Mutation(
        "PG-M01",
        "PG-CDC-001",
        Patch(
            SCANNER,
            "((self._fingerprint << 8) + byte - old) % PRIME",
            "((self._fingerprint << 8) + byte + old) % PRIME",
        ),
        "tests/test_streaming_parity.py::test_all_historical_source_vectors_match_with_changed_packetization",
    ),
    Mutation(
        "PG-M02",
        "PG-CDC-001",
        Patch(
            SCANNER,
            "self._buffer.clear()\n        self._start = self._offset",
            "self._buffer.clear()\n        self._window.clear()\n        self._fingerprint = 0\n"
            "        self._start = self._offset",
        ),
        SCANNER_TESTS + "test_short_tail_retains_rolling_window_across_cut",
    ),
    Mutation(
        "PG-M03",
        "PG-CDC-001",
        Patch(SCANNER, "return self._scan(bytes(view))", "return self._scan(view)"),
        SCANNER_TESTS + "test_mutable_packet_is_snapshotted_and_partial_feed_aborts",
    ),
    Mutation(
        "PG-M04",
        "PG-CDC-001",
        Patch(SCANNER, "if view.nbytes > self.policy.max_packet_bytes:", "if view.nbytes < 0:"),
        SCANNER_TESTS + "test_invalid_packet_capacity_and_released_views",
    ),
    Mutation(
        "PG-M09",
        "PG-CHECKPOINT-001",
        Patch(
            SOURCE + "checkpoints_lua.py",
            "if #a~=#b then return #a<#b and -1 or 1 end\n if a==b then return 0 end\n return a<b and -1 or 1",
            "local left,right=tonumber(a),tonumber(b)\n if left==right then return 0 end\n"
            " return left<right and -1 or 1",
        ),
        "tests/test_checkpoints_cache.py::test_redis_ordering_above_float_precision",
    ),
    Mutation(
        "PG-M10",
        "PG-CHECKPOINT-001",
        Patch(
            SOURCE + "checkpoints.py",
            "return snapshot if cached == encoded else None",
            "return snapshot if cached is not None else None",
        ),
        "tests/test_checkpoints_cache.py::test_foreign_scope_and_loss_are_rejected",
    ),
    Mutation(
        "PG-M11",
        "PG-OUTBOX-001",
        Patch(
            SOURCE + "outbox.py",
            "if current is None or current.epoch != identity.epoch:",
            "if current is None:",
        ),
        "tests/test_outbox_recovery.py::test_cache_loss_rebuild_requires_current_same_epoch_authority",
    ),
    Mutation(
        "PG-M12",
        "PG-PACE-001",
        Patch(
            SOURCE + "pace.py",
            "    require_operation(state, operation)\n    return action()",
            "    return action()",
        ),
        "tests/test_mutation_witnesses.py::test_pace_guard_precedes_callback",
    ),
)

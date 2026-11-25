-- PG-PEER-001 and PG-CONFIG-001: execute after migrations as the schema owner.
GRANT USAGE ON SCHEMA hmt_pg TO hmt_peer_a;
GRANT EXECUTE ON FUNCTION hmt_pg.own_identity() TO hmt_peer_a;
GRANT EXECUTE ON FUNCTION hmt_pg.admit_chunk(jsonb,bytea) TO hmt_peer_a;
GRANT EXECUTE ON FUNCTION hmt_pg.read_checkpoint(uuid) TO hmt_peer_a;
GRANT EXECUTE ON FUNCTION hmt_pg.claim_checkpoint() TO hmt_peer_a;
GRANT EXECUTE ON FUNCTION hmt_pg.finish_checkpoint(uuid,uuid,text) TO hmt_peer_a;
GRANT EXECUTE ON FUNCTION hmt_pg.recover_checkpoints(integer) TO hmt_peer_a;
GRANT EXECUTE ON FUNCTION hmt_pg.checkpoint_for_claim(uuid,uuid) TO hmt_peer_a;
GRANT USAGE ON SCHEMA hmt_pg TO hmt_metrics_reader,hmt_metrics_writer;
GRANT SELECT ON hmt_pg.metrics TO hmt_metrics_reader;
GRANT SELECT,INSERT ON hmt_pg.metrics TO hmt_metrics_writer;

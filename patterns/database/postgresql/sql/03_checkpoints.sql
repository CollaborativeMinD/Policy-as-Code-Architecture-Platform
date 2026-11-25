-- PG-CKPT/OUTBOX: dependent on immutable authority/effect schema in migration02.
CREATE FUNCTION hmt_pg.read_checkpoint(sid uuid)
RETURNS TABLE(db_role text,stream_id uuid,epoch bigint,sequence bigint,end_offset bigint,digest bytea,policy_digest bytea)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,hmt_pg AS $$
DECLARE a hmt_pg.peer_authority;
BEGIN
 a:=hmt_pg.authority_for(NULL);
 RETURN QUERY SELECT s.db_role::text,s.stream_id,s.epoch,s.sequence,s.end_offset,s.digest,s.policy_digest
  FROM hmt_pg.stream_head s WHERE s.db_role=a.db_role AND s.stream_id=sid AND s.sequence>=0;
END $$;
CREATE FUNCTION hmt_pg.claim_checkpoint()
RETURNS TABLE(event_id uuid,claim_id uuid,db_role text,stream_id uuid,epoch bigint,sequence bigint,
 end_offset bigint,digest bytea,policy_digest bytea)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,hmt_pg AS $$
DECLARE a hmt_pg.peer_authority; event hmt_pg.checkpoint_outbox; token uuid:=gen_random_uuid();
BEGIN
 a:=hmt_pg.authority_for(NULL);
 SELECT * INTO event FROM hmt_pg.checkpoint_outbox o WHERE o.db_role=a.db_role AND o.epoch=a.epoch AND o.state='PENDING'
  ORDER BY o.sequence,o.event_id LIMIT 1 FOR UPDATE SKIP LOCKED;
 IF NOT FOUND THEN RETURN; END IF;
 IF a.expires_at<=clock_timestamp() THEN RAISE EXCEPTION 'AUTHORITY_EXPIRED'; END IF;
 UPDATE hmt_pg.checkpoint_outbox o SET state='DISPATCHING',claim_id=token WHERE o.event_id=event.event_id;
 RETURN QUERY SELECT event.event_id,token,event.db_role::text,event.stream_id,event.epoch,event.sequence,
  event.end_offset,event.digest,event.policy_digest;
END $$;
CREATE FUNCTION hmt_pg.finish_checkpoint(eid uuid,token uuid,outcome text) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,hmt_pg AS $$
BEGIN
 IF outcome NOT IN ('ACKED','UNKNOWN') OR outcome IS NULL THEN RAISE EXCEPTION 'INVALID_OUTCOME'; END IF;
 UPDATE hmt_pg.checkpoint_outbox SET state=outcome WHERE event_id=eid AND db_role=session_user AND
  claim_id=token AND state IN ('DISPATCHING','UNKNOWN');
 RETURN FOUND;
END $$;
-- Receipt observation remains available after revocation; admission and claims do not.
CREATE FUNCTION hmt_pg.recover_checkpoints(cap integer)
RETURNS TABLE(event_id uuid,claim_id uuid,db_role text,stream_id uuid,epoch bigint,sequence bigint,
 end_offset bigint,digest bytea,policy_digest bytea)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,hmt_pg AS $$
BEGIN
 IF cap IS NULL OR cap<1 OR cap>100 THEN RAISE EXCEPTION 'INVALID_RECOVERY_LIMIT'; END IF;
 RETURN QUERY SELECT o.event_id,o.claim_id,o.db_role::text,o.stream_id,o.epoch,o.sequence,o.end_offset,o.digest,o.policy_digest
  FROM hmt_pg.checkpoint_outbox o WHERE o.db_role=session_user AND o.state IN ('DISPATCHING','UNKNOWN')
  ORDER BY o.sequence,o.event_id LIMIT cap;
END $$;
CREATE FUNCTION hmt_pg.checkpoint_for_claim(eid uuid,token uuid)
RETURNS TABLE(db_role text,stream_id uuid,epoch bigint,sequence bigint,end_offset bigint,digest bytea,policy_digest bytea)
LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,hmt_pg AS $$
 SELECT s.db_role::text,s.stream_id,s.epoch,s.sequence,s.end_offset,s.digest,s.policy_digest
 FROM hmt_pg.checkpoint_outbox o JOIN hmt_pg.stream_head s USING(db_role,stream_id)
 WHERE o.event_id=eid AND o.claim_id=token AND o.db_role=session_user AND o.state IN ('DISPATCHING','UNKNOWN')
$$;
CREATE FUNCTION hmt_pg.reject_effect_change() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,hmt_pg AS $$
BEGIN RAISE EXCEPTION 'IMMUTABLE_EFFECT'; END $$;
CREATE TRIGGER immutable_chunk BEFORE UPDATE OR DELETE ON hmt_pg.chunk_effect
 FOR EACH ROW EXECUTE FUNCTION hmt_pg.reject_effect_change();
CREATE FUNCTION hmt_pg.guard_authority_epoch() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,hmt_pg AS $$
BEGIN
 IF NEW.epoch<=OLD.epoch THEN RAISE EXCEPTION 'EPOCH_MUST_ADVANCE'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER monotone_authority BEFORE UPDATE ON hmt_pg.peer_authority
 FOR EACH ROW EXECUTE FUNCTION hmt_pg.guard_authority_epoch();
REVOKE ALL ON hmt_pg.peer_authority,hmt_pg.stream_head,hmt_pg.chunk_effect,hmt_pg.checkpoint_outbox FROM PUBLIC;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA hmt_pg FROM PUBLIC;

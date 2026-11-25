-- PG-AUTH-01..06. Owned by a non-login migration role in deployment.
-- Application LOGIN roles receive only the explicitly enumerated entry points.
CREATE TABLE hmt_pg.peer_authority (
 db_role name PRIMARY KEY, peer_key text UNIQUE NOT NULL CHECK (peer_key ~ '^nodekey:[0-9a-f]{64}$'),
 epoch bigint NOT NULL CHECK(epoch>0), active boolean NOT NULL, expires_at timestamptz NOT NULL
);
CREATE TABLE hmt_pg.stream_head (
 db_role name NOT NULL REFERENCES hmt_pg.peer_authority, stream_id uuid NOT NULL,
 epoch bigint NOT NULL, sequence bigint NOT NULL DEFAULT -1, end_offset bigint NOT NULL DEFAULT 0,
 digest bytea NOT NULL DEFAULT decode(repeat('00',32),'hex'), policy_digest bytea NOT NULL,
 PRIMARY KEY(db_role,stream_id), CHECK(octet_length(digest)=32 AND octet_length(policy_digest)=32)
);
CREATE TABLE hmt_pg.chunk_effect (
 db_role name NOT NULL REFERENCES hmt_pg.peer_authority, stream_id uuid NOT NULL, request_id uuid NOT NULL,
 epoch bigint NOT NULL CHECK(epoch>0), sequence bigint NOT NULL CHECK(sequence>=0), start_offset bigint NOT NULL,
 end_offset bigint NOT NULL, previous_digest bytea NOT NULL, digest bytea NOT NULL, policy_digest bytea NOT NULL,
 payload bytea NOT NULL, PRIMARY KEY(db_role,stream_id,sequence), UNIQUE(db_role,request_id),
 CHECK(start_offset>=0 AND end_offset>start_offset AND end_offset-start_offset=octet_length(payload)),
 CHECK(octet_length(payload) BETWEEN 1 AND 1048576),
 CHECK(octet_length(previous_digest)=32 AND octet_length(digest)=32 AND octet_length(policy_digest)=32)
);
CREATE TABLE hmt_pg.checkpoint_outbox (
 event_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), db_role name NOT NULL, request_id uuid NOT NULL,
 stream_id uuid NOT NULL, epoch bigint NOT NULL, sequence bigint NOT NULL, end_offset bigint NOT NULL,
 digest bytea NOT NULL, policy_digest bytea NOT NULL, state text NOT NULL DEFAULT 'PENDING', claim_id uuid,
 UNIQUE(db_role,request_id), FOREIGN KEY(db_role,request_id) REFERENCES hmt_pg.chunk_effect(db_role,request_id),
 CHECK(state IN ('PENDING','DISPATCHING','ACKED','UNKNOWN'))
);
CREATE INDEX checkpoint_pending ON hmt_pg.checkpoint_outbox(db_role,sequence) WHERE state='PENDING';
CREATE TYPE hmt_pg.chunk_input AS (
 stream_id uuid, request_id uuid, epoch bigint, sequence bigint, start_offset bigint,
 previous_digest bytea, policy_digest bytea
);
CREATE FUNCTION hmt_pg.parse_chunk(h jsonb,p bytea) RETURNS hmt_pg.chunk_input
LANGUAGE plpgsql SET search_path=pg_catalog,hmt_pg AS $$
DECLARE v hmt_pg.chunk_input;
BEGIN
 IF h IS NULL OR p IS NULL OR jsonb_typeof(h)<>'object' OR octet_length(p) NOT BETWEEN 1 AND 1048576 THEN
  RAISE EXCEPTION 'INVALID_CHUNK'; END IF;
 IF (SELECT array_agg(key ORDER BY key) FROM jsonb_object_keys(h) key) <>
  ARRAY['epoch','policy_digest','previous_digest','request_id','sequence','start','stream_id'] THEN
  RAISE EXCEPTION 'INVALID_HEADER'; END IF;
 IF jsonb_typeof(h->'epoch')<>'number' OR jsonb_typeof(h->'sequence')<>'number' OR
  jsonb_typeof(h->'start')<>'number' OR (h->>'previous_digest') !~ '^[0-9a-f]{64}$' OR
  (h->>'policy_digest') !~ '^[0-9a-f]{64}$' THEN RAISE EXCEPTION 'INVALID_HEADER'; END IF;
 IF jsonb_typeof(h->'stream_id')<>'string' OR jsonb_typeof(h->'request_id')<>'string' OR
  jsonb_typeof(h->'previous_digest')<>'string' OR jsonb_typeof(h->'policy_digest')<>'string' THEN
  RAISE EXCEPTION 'INVALID_HEADER'; END IF;
 v := ROW((h->>'stream_id')::uuid,(h->>'request_id')::uuid,(h->>'epoch')::bigint,
  (h->>'sequence')::bigint,(h->>'start')::bigint,decode(h->>'previous_digest','hex'),decode(h->>'policy_digest','hex'));
 IF v.epoch IS NULL OR v.epoch<1 OR v.sequence IS NULL OR v.sequence<0 OR v.start_offset IS NULL OR
  v.start_offset<0 OR v.stream_id IS NULL OR v.request_id IS NULL OR v.previous_digest IS NULL OR
  v.policy_digest IS NULL THEN RAISE EXCEPTION 'INVALID_HEADER'; END IF;
 RETURN v;
END $$;
CREATE FUNCTION hmt_pg.authority_for(expected bigint) RETURNS hmt_pg.peer_authority
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,hmt_pg AS $$
DECLARE a hmt_pg.peer_authority;
BEGIN
 SELECT * INTO a FROM hmt_pg.peer_authority WHERE db_role=session_user FOR UPDATE;
 IF NOT FOUND OR NOT a.active OR (expected IS NOT NULL AND a.epoch<>expected) OR
  a.expires_at<=clock_timestamp() THEN RAISE EXCEPTION 'AUTHORITY_DENIED'; END IF;
 RETURN a;
END $$;
CREATE FUNCTION hmt_pg.own_identity() RETURNS TABLE(db_role text,peer_key text,epoch bigint)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,hmt_pg AS $$
DECLARE a hmt_pg.peer_authority;
BEGIN
 a:=hmt_pg.authority_for(NULL); RETURN QUERY SELECT a.db_role::text,a.peer_key,a.epoch;
END $$;
CREATE FUNCTION hmt_pg.chunk_digest(a name,v hmt_pg.chunk_input,p bytea) RETURNS bytea
LANGUAGE sql IMMUTABLE SET search_path=pg_catalog,hmt_pg AS $$
 SELECT sha256(convert_to('hmt-pg-chunk-v1','UTF8')||int4send(octet_length(convert_to(a::text,'UTF8')))||
  convert_to(a::text,'UTF8')||uuid_send(v.stream_id)||int8send(v.epoch)||int8send(v.sequence)||
  int8send(v.start_offset)||v.policy_digest||v.previous_digest||p)
$$;
CREATE FUNCTION hmt_pg.admit_chunk(h jsonb,p bytea)
RETURNS TABLE(stream_id uuid,request_id uuid,epoch bigint,sequence bigint,start_offset bigint,end_offset bigint,
 digest bytea,policy_digest bytea,replayed boolean)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,hmt_pg AS $$
DECLARE v hmt_pg.chunk_input; a hmt_pg.peer_authority; e hmt_pg.chunk_effect; head hmt_pg.stream_head; d bytea;
BEGIN
 v:=hmt_pg.parse_chunk(h,p); a:=hmt_pg.authority_for(v.epoch);
 SELECT * INTO e FROM hmt_pg.chunk_effect c WHERE c.db_role=a.db_role AND c.request_id=v.request_id;
 IF FOUND THEN
  IF ROW(e.stream_id,e.epoch,e.sequence,e.start_offset,e.previous_digest,e.policy_digest,e.payload) IS DISTINCT FROM
   ROW(v.stream_id,v.epoch,v.sequence,v.start_offset,v.previous_digest,v.policy_digest,p) THEN
   RAISE EXCEPTION 'IDEMPOTENCY_CONFLICT'; END IF;
  IF a.expires_at<=clock_timestamp() THEN RAISE EXCEPTION 'AUTHORITY_EXPIRED'; END IF;
  RETURN QUERY SELECT e.stream_id,e.request_id,e.epoch,e.sequence,e.start_offset,e.end_offset,e.digest,e.policy_digest,true;
  RETURN;
 END IF;
 INSERT INTO hmt_pg.stream_head(db_role,stream_id,epoch,policy_digest) VALUES(a.db_role,v.stream_id,v.epoch,v.policy_digest)
  ON CONFLICT ON CONSTRAINT stream_head_pkey DO NOTHING;
 SELECT * INTO STRICT head FROM hmt_pg.stream_head s WHERE s.db_role=a.db_role AND s.stream_id=v.stream_id FOR UPDATE;
 IF ROW(head.epoch,head.sequence+1,head.end_offset,head.digest,head.policy_digest) IS DISTINCT FROM
  ROW(v.epoch,v.sequence,v.start_offset,v.previous_digest,v.policy_digest) THEN RAISE EXCEPTION 'CHECKPOINT_CONFLICT'; END IF;
 d:=hmt_pg.chunk_digest(a.db_role,v,p);
 IF a.expires_at<=clock_timestamp() THEN RAISE EXCEPTION 'AUTHORITY_EXPIRED'; END IF;
 INSERT INTO hmt_pg.chunk_effect VALUES(a.db_role,v.stream_id,v.request_id,v.epoch,v.sequence,v.start_offset,
  v.start_offset+octet_length(p),v.previous_digest,d,v.policy_digest,p);
 UPDATE hmt_pg.stream_head s SET sequence=v.sequence,end_offset=v.start_offset+octet_length(p),digest=d
  WHERE s.db_role=a.db_role AND s.stream_id=v.stream_id;
 INSERT INTO hmt_pg.checkpoint_outbox(db_role,request_id,stream_id,epoch,sequence,end_offset,digest,policy_digest)
  VALUES(a.db_role,v.request_id,v.stream_id,v.epoch,v.sequence,v.start_offset+octet_length(p),d,v.policy_digest);
 RETURN QUERY SELECT v.stream_id,v.request_id,v.epoch,v.sequence,v.start_offset,v.start_offset+octet_length(p),d,v.policy_digest,false;
END $$;
REVOKE ALL ON hmt_pg.peer_authority,hmt_pg.stream_head,hmt_pg.chunk_effect,hmt_pg.checkpoint_outbox FROM PUBLIC;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA hmt_pg FROM PUBLIC;

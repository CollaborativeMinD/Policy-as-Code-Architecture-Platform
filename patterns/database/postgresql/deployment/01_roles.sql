-- PG-PEER-001: owner-controlled provisioning; run only in the selected deployment.
-- Run role creation before migrations; 02_grants.sql follows migrations.
CREATE ROLE hmt_pg_owner NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
CREATE ROLE hmt_peer_a LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS CONNECTION LIMIT 4;
-- Provision SCRAM credentials outside this source. Never grant hmt_pg_owner to hmt_peer_a.
-- The administrator creates hmt_pg owned by hmt_pg_owner; run migrations under that owner.
CREATE ROLE hmt_metrics_reader LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS CONNECTION LIMIT 4;
CREATE ROLE hmt_metrics_writer LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS CONNECTION LIMIT 4;

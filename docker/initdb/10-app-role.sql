-- Local development: create the non-superuser role the application connects as.
--
-- The container's POSTGRES_USER (bitlux) is a SUPERUSER, and superusers bypass
-- Row-Level Security unconditionally -- FORCE ROW LEVEL SECURITY does not bind
-- them. So connecting as bitlux makes the tenant-isolation policies inert and
-- any "isolation works" test run as bitlux is meaningless.
--
-- bitlux      -> owns the schema, runs migrations. Superuser. RLS does not apply.
-- bitlux_app  -> owns nothing, no BYPASSRLS. RLS applies. This is the runtime role.
--
-- Migration 001 would create bitlux_app NOLOGIN if it did not exist; creating it
-- here first, with LOGIN and a dev password, is what lets `psql -U bitlux_app`
-- work locally. Production makes the same split. See DATA_MODEL.md 1.7.
--
-- Runs once, on first initialisation of the data volume.

CREATE ROLE bitlux_app
    LOGIN
    PASSWORD 'bitlux_app'
    NOSUPERUSER
    NOCREATEDB
    NOCREATEROLE
    NOBYPASSRLS
    INHERIT;

GRANT CONNECT ON DATABASE bitlux_crm TO bitlux_app;
GRANT USAGE ON SCHEMA public TO bitlux_app;

-- Safety-net default for anything bitlux creates outside the migration chain
-- (an ad-hoc table in a psql session, say): READ + APPEND only. UPDATE/DELETE
-- are never a default -- each migration grants them explicitly, per table, via
-- grant_app_dml(), so "append-only" is the floor and every exception is a
-- greppable line. audit_logs never receives one.
ALTER DEFAULT PRIVILEGES FOR ROLE bitlux IN SCHEMA public
    GRANT SELECT, INSERT ON TABLES TO bitlux_app;
ALTER DEFAULT PRIVILEGES FOR ROLE bitlux IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO bitlux_app;

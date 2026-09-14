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
-- Production must make the same split. See DATA_MODEL.md 1.7.
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

-- Grant DML on every table bitlux creates from now on, so each new migration
-- does not have to remember to grant. Applies to tables created *after* this
-- statement, which is every table in migrations 003-015.
ALTER DEFAULT PRIVILEGES FOR ROLE bitlux IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO bitlux_app;
ALTER DEFAULT PRIVILEGES FOR ROLE bitlux IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO bitlux_app;

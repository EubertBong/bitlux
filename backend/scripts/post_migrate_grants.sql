-- Run AFTER `alembic upgrade head`, as the schema owner.
--
-- ALTER DEFAULT PRIVILEGES (docker/initdb/10-app-role.sql) grants the app role
-- full DML on every new table, including audit_logs. That is wrong for an
-- append-only table, so take it back here.
--
-- The trigger from migration 013 already blocks UPDATE/DELETE on audit_logs even
-- for the owner; this is defence in depth at the privilege layer, and it is what
-- a privilege audit will look for.
--
-- Usage:
--   docker compose exec -T postgres psql -U bitlux -d bitlux_crm \
--     < backend/scripts/post_migrate_grants.sql

REVOKE UPDATE, DELETE, TRUNCATE ON audit_logs FROM bitlux_app;

-- Partitions inherit nothing privilege-wise; revoke on each explicitly.
DO $$
DECLARE r record;
BEGIN
    FOR r IN
        SELECT c.relname
        FROM pg_class c
        JOIN pg_inherits i ON i.inhrelid = c.oid
        WHERE i.inhparent = 'audit_logs'::regclass
    LOOP
        EXECUTE format('REVOKE UPDATE, DELETE, TRUNCATE ON %I FROM bitlux_app', r.relname);
    END LOOP;
END $$;

SELECT 'audit_logs privileges for bitlux_app:' AS check,
       coalesce(string_agg(privilege_type, ', ' ORDER BY privilege_type), '(none)') AS granted
FROM information_schema.table_privileges
WHERE grantee = 'bitlux_app' AND table_name = 'audit_logs';

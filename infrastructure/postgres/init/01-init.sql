-- Runs once, on the container's first start with an empty data volume
-- (docker-entrypoint-initdb.d convention). Written idempotently anyway,
-- since psql scripts here can be re-run manually against an existing volume.

CREATE EXTENSION IF NOT EXISTS postgis;

-- CREATE DATABASE cannot run inside a transaction or DO block, so the
-- conditional check has to happen client-side via \gexec: only feed the
-- CREATE DATABASE statement to psql when the database is missing.
SELECT 'CREATE DATABASE community_roots_test'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'community_roots_test')
\gexec

-- The test suite runs geospatial queries too, so the test database needs
-- its own PostGIS extension — extensions are not shared across databases.
\c community_roots_test
CREATE EXTENSION IF NOT EXISTS postgis;

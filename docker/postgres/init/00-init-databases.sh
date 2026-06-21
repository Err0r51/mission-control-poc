#!/usr/bin/env bash
set -euo pipefail

psql_base_args=(
  --username "${POSTGRES_USER}"
  --dbname postgres
  --set ON_ERROR_STOP=1
)

psql "${psql_base_args[@]}" \
  --set prefect_db="${PREFECT_DB_NAME}" \
  --set metabase_db="${METABASE_DB_NAME}" \
  --set warehouse_db="${WAREHOUSE_DB_NAME}" <<'SQL'
SELECT format('CREATE DATABASE %I', :'prefect_db')
WHERE NOT EXISTS (
  SELECT 1
  FROM pg_database
  WHERE datname = :'prefect_db'
)\gexec

SELECT format('CREATE DATABASE %I', :'metabase_db')
WHERE NOT EXISTS (
  SELECT 1
  FROM pg_database
  WHERE datname = :'metabase_db'
)\gexec

SELECT format('CREATE DATABASE %I', :'warehouse_db')
WHERE NOT EXISTS (
  SELECT 1
  FROM pg_database
  WHERE datname = :'warehouse_db'
)\gexec
SQL

psql \
  --username "${POSTGRES_USER}" \
  --dbname "${WAREHOUSE_DB_NAME}" \
  --set ON_ERROR_STOP=1 \
  --set admin_user="${POSTGRES_USER}" \
  --set warehouse_db="${WAREHOUSE_DB_NAME}" \
  --set warehouse_user="${WAREHOUSE_DB_USER}" \
  --set warehouse_password="${WAREHOUSE_DB_PASSWORD}" \
  --set metabase_user="${METABASE_WAREHOUSE_USER}" \
  --set metabase_password="${METABASE_WAREHOUSE_PASSWORD}" <<'SQL'
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'warehouse_user', :'warehouse_password')
WHERE NOT EXISTS (
  SELECT 1
  FROM pg_roles
  WHERE rolname = :'warehouse_user'
)\gexec

SELECT format('ALTER ROLE %I LOGIN PASSWORD %L', :'warehouse_user', :'warehouse_password')
WHERE EXISTS (
  SELECT 1
  FROM pg_roles
  WHERE rolname = :'warehouse_user'
)\gexec

SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'metabase_user', :'metabase_password')
WHERE NOT EXISTS (
  SELECT 1
  FROM pg_roles
  WHERE rolname = :'metabase_user'
)\gexec

SELECT format('ALTER ROLE %I LOGIN PASSWORD %L', :'metabase_user', :'metabase_password')
WHERE EXISTS (
  SELECT 1
  FROM pg_roles
  WHERE rolname = :'metabase_user'
)\gexec

SELECT format('REVOKE ALL ON DATABASE %I FROM PUBLIC', :'warehouse_db')\gexec
REVOKE ALL ON SCHEMA public FROM PUBLIC;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;

CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS analytics;

REVOKE ALL ON SCHEMA raw FROM PUBLIC;
REVOKE ALL ON SCHEMA analytics FROM PUBLIC;

SELECT format('GRANT CONNECT ON DATABASE %I TO %I', :'warehouse_db', :'warehouse_user')\gexec
SELECT format('GRANT CONNECT ON DATABASE %I TO %I', :'warehouse_db', :'metabase_user')\gexec

SELECT format('GRANT USAGE, CREATE ON SCHEMA raw TO %I', :'warehouse_user')\gexec
SELECT format('GRANT USAGE, CREATE ON SCHEMA analytics TO %I', :'warehouse_user')\gexec
SELECT format('GRANT USAGE ON SCHEMA analytics TO %I', :'metabase_user')\gexec

SELECT format('GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA raw TO %I', :'warehouse_user')\gexec
SELECT format('GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA analytics TO %I', :'warehouse_user')\gexec
SELECT format('GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA raw TO %I', :'warehouse_user')\gexec
SELECT format('GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA analytics TO %I', :'warehouse_user')\gexec
SELECT format('GRANT SELECT ON ALL TABLES IN SCHEMA analytics TO %I', :'metabase_user')\gexec

SELECT format(
  'ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA raw GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER ON TABLES TO %I',
  :'admin_user',
  :'warehouse_user'
)\gexec
SELECT format(
  'ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA analytics GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER ON TABLES TO %I',
  :'admin_user',
  :'warehouse_user'
)\gexec
SELECT format(
  'ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA raw GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO %I',
  :'admin_user',
  :'warehouse_user'
)\gexec
SELECT format(
  'ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA analytics GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO %I',
  :'admin_user',
  :'warehouse_user'
)\gexec
SELECT format(
  'ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA analytics GRANT SELECT ON TABLES TO %I',
  :'admin_user',
  :'metabase_user'
)\gexec
SELECT format(
  'ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA analytics GRANT SELECT ON TABLES TO %I',
  :'warehouse_user',
  :'metabase_user'
)\gexec
SQL

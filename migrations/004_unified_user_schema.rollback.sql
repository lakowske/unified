-- Rollback for unified user schema migration
-- This removes all tables, views, functions, and triggers created in the migration

-- Drop views first (they depend on tables)
DROP VIEW IF EXISTS unified.apache_auth CASCADE;
DROP VIEW IF EXISTS unified.dovecot_auth CASCADE;
DROP VIEW IF EXISTS unified.dovecot_users CASCADE;

-- Drop triggers
DROP TRIGGER IF EXISTS trigger_extract_domain_from_email_v2 ON unified.users_v2 CASCADE;
DROP TRIGGER IF EXISTS trigger_users_v2_updated_at ON unified.users_v2 CASCADE;

-- Drop functions
DROP FUNCTION IF EXISTS unified.extract_domain_from_email_v2() CASCADE;
DROP FUNCTION IF EXISTS unified.update_updated_at_column_v2() CASCADE;

-- Drop tables in reverse dependency order
DROP TABLE IF EXISTS unified.audit_log_v2 CASCADE;
DROP TABLE IF EXISTS unified.email_aliases CASCADE;
DROP TABLE IF EXISTS unified.user_quotas CASCADE;
DROP TABLE IF EXISTS unified.user_roles CASCADE;
DROP TABLE IF EXISTS unified.user_passwords CASCADE;
DROP TABLE IF EXISTS unified.users_v2 CASCADE;

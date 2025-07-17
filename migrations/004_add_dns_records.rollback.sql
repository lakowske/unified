-- Rollback for add dns records (migration 004)
-- This reverses all changes made in 004_add_dns_records.sql

-- Drop objects in reverse dependency order
DROP INDEX IF EXISTS IF CASCADE;
DROP INDEX IF EXISTS IF CASCADE;
DROP INDEX IF EXISTS for CASCADE;
DROP TRIGGER IF EXISTS dns_record_update_serial ON unified.dns_records CASCADE;
DROP FUNCTION IF EXISTS unified.update_dns_zone_serial() CASCADE;
DROP TABLE IF EXISTS IF CASCADE;
DROP TABLE IF EXISTS IF CASCADE;

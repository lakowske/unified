-- Rollback Certificate Management System Migration
-- Removes all certificate management tables, views, functions, and triggers

-- ================================================================
-- DROP TRIGGERS AND FUNCTIONS
-- ================================================================

-- Drop triggers first
DROP TRIGGER IF EXISTS trigger_certificate_notifications ON unified.certificates;
DROP TRIGGER IF EXISTS trigger_certificates_updated_at ON unified.certificates;

-- Drop functions
DROP FUNCTION IF EXISTS unified.notify_certificate_change();
DROP FUNCTION IF EXISTS unified.update_certificate_timestamp();
DROP FUNCTION IF EXISTS unified.check_certificate_expiration();

-- ================================================================
-- DROP VIEWS
-- ================================================================

DROP VIEW IF EXISTS unified.certificate_file_status;
DROP VIEW IF EXISTS unified.certificate_status;

-- ================================================================
-- DROP TABLES (in reverse dependency order)
-- ================================================================

-- Drop tables with foreign keys first
DROP TABLE IF EXISTS unified.certificate_renewals;
DROP TABLE IF EXISTS unified.certificate_notifications;
DROP TABLE IF EXISTS unified.certificate_files;

-- Drop main certificate table last
DROP TABLE IF EXISTS unified.certificates;

-- ================================================================
-- CLEANUP
-- ================================================================

-- Note: This rollback removes all certificate management functionality
-- Any existing certificate data will be permanently lost
-- Make sure to backup certificate data before running this rollback

-- Rollback for add user creation notify (migration 002)
-- This reverses all changes made in 002_add_user_creation_notify.sql

-- Drop objects in reverse dependency order
DROP INDEX IF EXISTS idx_mailbox_events_type CASCADE;
DROP INDEX IF EXISTS idx_mailbox_events_user_id CASCADE;
DROP INDEX IF EXISTS idx_mailbox_events_processed CASCADE;
DROP TRIGGER IF EXISTS trigger_notify_user_deleted ON unified.users CASCADE;
DROP TRIGGER IF EXISTS trigger_notify_user_updated ON unified.users CASCADE;
DROP TRIGGER IF EXISTS trigger_notify_user_created ON unified.users CASCADE;
DROP FUNCTION IF EXISTS unified.notify_user_deleted() CASCADE;
DROP FUNCTION IF EXISTS unified.notify_user_updated() CASCADE;
DROP FUNCTION IF EXISTS unified.notify_user_created() CASCADE;
DROP TABLE IF EXISTS unified.mailbox_events CASCADE;

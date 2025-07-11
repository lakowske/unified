-- Rollback for user table migration
-- This removes the users table and its indexes

DROP TABLE IF EXISTS unified.users CASCADE;

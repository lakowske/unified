-- Migration: Add LISTEN/NOTIFY for automatic mailbox creation
-- This adds database triggers to notify the mail container when users are created

-- ================================================================
-- NOTIFICATION FUNCTION FOR USER CREATION
-- ================================================================

-- Function to send notification when a user is created
CREATE OR REPLACE FUNCTION unified.notify_user_created()
RETURNS TRIGGER AS $$
BEGIN
    -- Send notification with user details as JSON payload
    PERFORM pg_notify(
        'user_created',
        json_build_object(
            'user_id', NEW.id,
            'username', NEW.username,
            'email', NEW.email,
            'domain', NEW.domain,
            'home_directory', NEW.home_directory,
            'created_at', NEW.created_at
        )::text
    );
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ================================================================
-- NOTIFICATION TRIGGER
-- ================================================================

-- Trigger to automatically notify when a user is created
CREATE TRIGGER trigger_notify_user_created
    AFTER INSERT ON unified.users
    FOR EACH ROW
    EXECUTE FUNCTION unified.notify_user_created();

-- ================================================================
-- NOTIFICATION FUNCTION FOR USER UPDATES
-- ================================================================

-- Function to send notification when a user is updated (in case of email/domain changes)
CREATE OR REPLACE FUNCTION unified.notify_user_updated()
RETURNS TRIGGER AS $$
BEGIN
    -- Only notify if email or domain changed (mailbox location might need to change)
    IF NEW.email != OLD.email OR NEW.domain != OLD.domain OR NEW.home_directory != OLD.home_directory THEN
        PERFORM pg_notify(
            'user_updated',
            json_build_object(
                'user_id', NEW.id,
                'username', NEW.username,
                'old_email', OLD.email,
                'new_email', NEW.email,
                'old_domain', OLD.domain,
                'new_domain', NEW.domain,
                'old_home_directory', OLD.home_directory,
                'new_home_directory', NEW.home_directory,
                'updated_at', NEW.updated_at
            )::text
        );
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to automatically notify when a user is updated
CREATE TRIGGER trigger_notify_user_updated
    AFTER UPDATE ON unified.users
    FOR EACH ROW
    EXECUTE FUNCTION unified.notify_user_updated();

-- ================================================================
-- NOTIFICATION FUNCTION FOR USER DELETION
-- ================================================================

-- Function to send notification when a user is deleted (for mailbox cleanup)
CREATE OR REPLACE FUNCTION unified.notify_user_deleted()
RETURNS TRIGGER AS $$
BEGIN
    PERFORM pg_notify(
        'user_deleted',
        json_build_object(
            'user_id', OLD.id,
            'username', OLD.username,
            'email', OLD.email,
            'domain', OLD.domain,
            'home_directory', OLD.home_directory,
            'deleted_at', now()
        )::text
    );
    
    RETURN OLD;
END;
$$ LANGUAGE plpgsql;

-- Trigger to automatically notify when a user is deleted
CREATE TRIGGER trigger_notify_user_deleted
    AFTER DELETE ON unified.users
    FOR EACH ROW
    EXECUTE FUNCTION unified.notify_user_deleted();

-- ================================================================
-- LOGGING TABLE FOR NOTIFICATION EVENTS (OPTIONAL)
-- ================================================================

-- Table to log notification events for debugging and auditing
CREATE TABLE unified.mailbox_events (
    id SERIAL PRIMARY KEY,
    event_type VARCHAR(50) NOT NULL, -- 'created', 'updated', 'deleted'
    user_id INTEGER,
    username VARCHAR(255),
    email VARCHAR(255),
    domain VARCHAR(255),
    home_directory VARCHAR(500),
    event_data JSONB,
    processed BOOLEAN DEFAULT false,
    processed_at TIMESTAMP NULL,
    error_message TEXT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for efficient querying of unprocessed events
CREATE INDEX idx_mailbox_events_processed ON unified.mailbox_events(processed, created_at);
CREATE INDEX idx_mailbox_events_user_id ON unified.mailbox_events(user_id);
CREATE INDEX idx_mailbox_events_type ON unified.mailbox_events(event_type);
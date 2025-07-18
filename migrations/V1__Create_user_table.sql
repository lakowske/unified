-- Unified User Schema Migration for Apache/Dovecot Compatibility
-- This creates a comprehensive users schema supporting multiple services
-- with proper authentication and authorization for Apache, Dovecot, and future services

-- Create the unified schema if it doesn't exist
CREATE SCHEMA IF NOT EXISTS unified;

-- ================================================================
-- CORE USER IDENTITY TABLE
-- ================================================================
CREATE TABLE unified.users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(255) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    domain VARCHAR(255) NOT NULL, -- Extract domain for dovecot
    first_name VARCHAR(100),
    last_name VARCHAR(100),

    -- System mapping for dovecot
    system_uid INTEGER DEFAULT 5000, -- vmail user
    system_gid INTEGER DEFAULT 5000, -- vmail group
    home_directory VARCHAR(500), -- /var/mail/domain/username
    mailbox_format VARCHAR(20) DEFAULT 'maildir', -- maildir or mbox

    -- Account status
    is_active BOOLEAN DEFAULT true,
    is_locked BOOLEAN DEFAULT false,
    email_verified BOOLEAN DEFAULT false,

    -- Email verification
    email_verification_token VARCHAR(255) NULL,
    email_verification_expires_at TIMESTAMP NULL,

    -- Password reset
    password_reset_token VARCHAR(255) NULL,
    password_reset_expires_at TIMESTAMP NULL,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login_at TIMESTAMP NULL,
    failed_login_attempts INTEGER DEFAULT 0,
    last_failed_login_at TIMESTAMP NULL,

    -- Ensure domain is extracted from email
    CONSTRAINT domain_matches_email CHECK (email LIKE '%@' || domain)
);

-- ================================================================
-- SERVICE-COMPATIBLE PASSWORD STORAGE
-- ================================================================
CREATE TABLE unified.user_passwords (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES unified.users(id) ON DELETE CASCADE,
    service VARCHAR(50) NOT NULL,

    -- Password in format expected by service
    password_hash TEXT NOT NULL,
    hash_scheme VARCHAR(50) NOT NULL, -- PLAIN, CRYPT, SHA256, SSHA, BCRYPT, etc.

    -- Password policy tracking
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NULL,
    must_change_on_next_login BOOLEAN DEFAULT false,

    UNIQUE(user_id, service)
);

-- ================================================================
-- SIMPLIFIED ROLES FOR SERVICE COMPATIBILITY
-- ================================================================
CREATE TABLE unified.user_roles (
    user_id INTEGER REFERENCES unified.users(id) ON DELETE CASCADE,
    role_name VARCHAR(50) NOT NULL, -- 'admin', 'user', 'customer', 'no_email'
    service VARCHAR(50) NOT NULL,   -- 'apache', 'dovecot', 'webdav', 'samba'
    granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    granted_by INTEGER REFERENCES unified.users(id),
    PRIMARY KEY (user_id, service)
);

-- ================================================================
-- SERVICE QUOTAS AND LIMITS
-- ================================================================
CREATE TABLE unified.user_quotas (
    user_id INTEGER REFERENCES unified.users(id) ON DELETE CASCADE,
    service VARCHAR(50) NOT NULL,
    quota_type VARCHAR(50) NOT NULL, -- 'storage', 'bandwidth', 'connections'
    quota_value BIGINT, -- bytes, count, etc.
    quota_unit VARCHAR(20), -- 'bytes', 'MB', 'count'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, service, quota_type)
);

-- ================================================================
-- EMAIL ALIASES (for mail services)
-- ================================================================
CREATE TABLE unified.email_aliases (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES unified.users(id) ON DELETE CASCADE,
    alias_email VARCHAR(255) NOT NULL UNIQUE,
    is_primary BOOLEAN DEFAULT false,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ================================================================
-- AUDIT LOG
-- ================================================================
CREATE TABLE unified.audit_log (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES unified.users(id),
    service VARCHAR(50),
    action VARCHAR(100), -- 'login', 'logout', 'password_change', 'role_grant', etc.
    resource VARCHAR(500), -- what was accessed/modified
    ip_address INET,
    user_agent TEXT,
    success BOOLEAN,
    error_message TEXT,
    additional_data JSONB, -- flexible storage for service-specific data
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ================================================================
-- SERVICE-SPECIFIC INTEGRATION VIEWS
-- ================================================================

-- Apache Authentication View (for mod_authn_dbd)
CREATE VIEW unified.apache_auth AS
SELECT
    u.username,
    up.password_hash as password,
    CASE WHEN ur.role_name = 'admin' THEN 'admin'
         WHEN ur.role_name = 'user' THEN 'user'
         ELSE 'customer' END as role,
    u.is_active,
    u.email_verified
FROM unified.users u
JOIN unified.user_passwords up ON u.id = up.user_id
LEFT JOIN unified.user_roles ur ON u.id = ur.user_id AND ur.service = 'apache'
WHERE u.is_active = true
  AND u.email_verified = true
  AND up.service = 'apache';

-- Dovecot Password Authentication View
CREATE VIEW unified.dovecot_auth AS
SELECT
    u.username,
    u.domain,
    u.email as "user",
    up.password_hash as password,
    up.hash_scheme as scheme,
    u.is_active
FROM unified.users u
JOIN unified.user_passwords up ON u.id = up.user_id
LEFT JOIN unified.user_roles ur ON u.id = ur.user_id AND ur.service = 'dovecot'
WHERE u.is_active = true
  AND up.service = 'dovecot'
  AND (ur.role_name IS NULL OR ur.role_name != 'no_email'); -- Has email access

-- Dovecot User Info View
CREATE VIEW unified.dovecot_users AS
SELECT
    u.username,
    u.domain,
    u.email as "user",
    u.home_directory as home,
    u.system_uid as uid,
    u.system_gid as gid,
    u.mailbox_format,
    COALESCE(q.quota_value, 1073741824) as quota_bytes -- default 1GB
FROM unified.users u
LEFT JOIN unified.user_quotas q ON u.id = q.user_id
    AND q.service = 'dovecot'
    AND q.quota_type = 'storage'
WHERE u.is_active = true;

-- ================================================================
-- INDEXES FOR PERFORMANCE
-- ================================================================

-- Core user lookups
CREATE INDEX idx_users_email ON unified.users(email);
CREATE INDEX idx_users_username ON unified.users(username);
CREATE INDEX idx_users_domain ON unified.users(domain);
CREATE INDEX idx_users_active ON unified.users(is_active);

-- Password lookups
CREATE INDEX idx_user_passwords_service ON unified.user_passwords(service);
CREATE INDEX idx_user_passwords_user_service ON unified.user_passwords(user_id, service);

-- Role lookups
CREATE INDEX idx_user_roles_service ON unified.user_roles(service);
CREATE INDEX idx_user_roles_user_service ON unified.user_roles(user_id, service);

-- Audit queries
CREATE INDEX idx_audit_log_user_id ON unified.audit_log(user_id);
CREATE INDEX idx_audit_log_service ON unified.audit_log(service);
CREATE INDEX idx_audit_log_created_at ON unified.audit_log(created_at);

-- ================================================================
-- FUNCTIONS FOR COMMON OPERATIONS
-- ================================================================

-- Function to automatically extract domain from email
CREATE OR REPLACE FUNCTION unified.extract_domain_from_email()
RETURNS TRIGGER AS $$
BEGIN
    -- Extract domain from email address
    NEW.domain = split_part(NEW.email, '@', 2);

    -- Set default home directory if not provided
    IF NEW.home_directory IS NULL THEN
        NEW.home_directory = '/var/mail/' || NEW.domain || '/' || NEW.username;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to automatically set domain and home directory
CREATE TRIGGER trigger_extract_domain_from_email
    BEFORE INSERT OR UPDATE ON unified.users
    FOR EACH ROW
    EXECUTE FUNCTION unified.extract_domain_from_email();

-- Function to update timestamp on record changes
CREATE OR REPLACE FUNCTION unified.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to automatically update updated_at timestamp
CREATE TRIGGER trigger_users_updated_at
    BEFORE UPDATE ON unified.users
    FOR EACH ROW
    EXECUTE FUNCTION unified.update_updated_at_column();

-- ================================================================
-- PRODUCTION-READY SCHEMA
-- ================================================================
--
-- No sample data is included in this migration.
-- Users should be created via the admin API endpoints:
-- - POST /api/v1/admin/create_user.php
-- - Or via REST API: `curl -X POST http://localhost:8080/api/v1/admin/create_user`
--
-- This ensures proper password hashing and security practices.

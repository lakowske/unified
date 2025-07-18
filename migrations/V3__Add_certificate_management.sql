-- Certificate Management System Migration
-- Adds comprehensive SSL/TLS certificate tracking and notification system
-- Supports self-signed, Let's Encrypt, and manual certificate management

-- ================================================================
-- CERTIFICATE MANAGEMENT TABLES
-- ================================================================

-- Core certificate records table
CREATE TABLE unified.certificates (
    id SERIAL PRIMARY KEY,
    domain VARCHAR(255) NOT NULL,
    certificate_type VARCHAR(50) NOT NULL, -- 'self-signed', 'letsencrypt', 'manual'

    -- Certificate metadata
    subject_alt_names TEXT[], -- Additional domains covered by this certificate
    issuer VARCHAR(500),
    subject VARCHAR(500),

    -- Validity period
    not_before TIMESTAMP NOT NULL,
    not_after TIMESTAMP NOT NULL,

    -- Certificate paths (relative to /data/certificates/)
    certificate_path VARCHAR(500) NOT NULL, -- e.g., 'live/example.com/cert.pem'
    private_key_path VARCHAR(500) NOT NULL, -- e.g., 'live/example.com/privkey.pem'
    chain_path VARCHAR(500), -- e.g., 'live/example.com/chain.pem'
    fullchain_path VARCHAR(500), -- e.g., 'live/example.com/fullchain.pem'

    -- Status and renewal tracking
    is_active BOOLEAN DEFAULT true,
    auto_renew BOOLEAN DEFAULT true,
    renewal_attempts INTEGER DEFAULT 0,
    last_renewal_attempt TIMESTAMP NULL,
    last_renewal_success TIMESTAMP NULL,
    renewal_error_message TEXT NULL,

    -- Let's Encrypt specific
    acme_account_key_path VARCHAR(500) NULL,
    acme_staging BOOLEAN DEFAULT false,
    acme_challenge_type VARCHAR(50) DEFAULT 'http-01', -- 'http-01', 'dns-01'

    -- Creation and update tracking
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER REFERENCES unified.users(id),

    -- Constraints
    UNIQUE(domain, certificate_type),
    CHECK (certificate_type IN ('self-signed', 'letsencrypt', 'manual')),
    CHECK (not_after > not_before),
    CHECK (acme_challenge_type IN ('http-01', 'dns-01'))
);

-- Individual certificate files with integrity verification
CREATE TABLE unified.certificate_files (
    id SERIAL PRIMARY KEY,
    certificate_id INTEGER REFERENCES unified.certificates(id) ON DELETE CASCADE,

    -- File details
    file_type VARCHAR(50) NOT NULL, -- 'certificate', 'private_key', 'chain', 'fullchain'
    file_path VARCHAR(500) NOT NULL, -- Full path relative to /data/certificates/
    file_size BIGINT NOT NULL,
    file_checksum VARCHAR(64) NOT NULL, -- SHA256 checksum for integrity
    file_permissions VARCHAR(10) NOT NULL, -- e.g., '644', '600'

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_verified TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Constraints
    UNIQUE(certificate_id, file_type),
    CHECK (file_type IN ('certificate', 'private_key', 'chain', 'fullchain')),
    CHECK (file_permissions ~ '^[0-7]{3}$')
);

-- Certificate notification log for LISTEN/NOTIFY system
CREATE TABLE unified.certificate_notifications (
    id SERIAL PRIMARY KEY,
    certificate_id INTEGER REFERENCES unified.certificates(id) ON DELETE CASCADE,

    -- Notification details
    notification_type VARCHAR(50) NOT NULL, -- 'created', 'updated', 'renewed', 'expired', 'error'
    message TEXT,
    data JSONB, -- Additional structured data

    -- Processing status
    processed_at TIMESTAMP NULL,
    processed_by VARCHAR(100) NULL, -- Service that processed the notification

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CHECK (notification_type IN ('created', 'updated', 'renewed', 'expired', 'error', 'deleted'))
);

-- Certificate renewal schedule and history
CREATE TABLE unified.certificate_renewals (
    id SERIAL PRIMARY KEY,
    certificate_id INTEGER REFERENCES unified.certificates(id) ON DELETE CASCADE,

    -- Renewal scheduling
    scheduled_at TIMESTAMP NOT NULL,
    started_at TIMESTAMP NULL,
    completed_at TIMESTAMP NULL,

    -- Renewal details
    renewal_method VARCHAR(50) NOT NULL, -- 'automatic', 'manual', 'forced'
    success BOOLEAN NULL,
    error_message TEXT NULL,

    -- Before/after certificate details
    old_not_after TIMESTAMP NULL,
    new_not_after TIMESTAMP NULL,

    -- Renewal context
    triggered_by VARCHAR(100), -- 'cron', 'manual', 'api', 'expiration_check'
    renewal_logs TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CHECK (renewal_method IN ('automatic', 'manual', 'forced'))
);

-- Service certificate usage tracking
CREATE TABLE unified.service_certificates (
    id SERIAL PRIMARY KEY,
    service_name VARCHAR(100) NOT NULL, -- 'apache', 'mail', 'nginx', etc.
    domain VARCHAR(255) NOT NULL,
    certificate_type VARCHAR(50) NOT NULL, -- 'live', 'staged', 'self-signed', 'none'
    ssl_enabled BOOLEAN DEFAULT false,
    certificate_path VARCHAR(500),
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT true,

    -- Constraints
    UNIQUE(service_name, domain),
    CHECK (certificate_type IN ('live', 'staged', 'self-signed', 'none'))
);

-- Index for service certificate lookups
CREATE INDEX idx_service_certificates_service ON unified.service_certificates(service_name);
CREATE INDEX idx_service_certificates_domain ON unified.service_certificates(domain);
CREATE INDEX idx_service_certificates_type ON unified.service_certificates(certificate_type);
CREATE INDEX idx_service_certificates_active ON unified.service_certificates(is_active);

-- ================================================================
-- CERTIFICATE MANAGEMENT VIEWS
-- ================================================================

-- Active certificates with expiration status
CREATE VIEW unified.certificate_status AS
SELECT
    c.id,
    c.domain,
    c.certificate_type,
    c.subject_alt_names,
    c.issuer,
    c.not_before,
    c.not_after,
    c.is_active,
    c.auto_renew,
    c.last_renewal_success,
    c.renewal_error_message,

    -- Expiration calculations
    (c.not_after - CURRENT_TIMESTAMP) AS time_until_expiry,
    CASE
        WHEN c.not_after < CURRENT_TIMESTAMP THEN 'expired'
        WHEN c.not_after < (CURRENT_TIMESTAMP + INTERVAL '7 days') THEN 'critical'
        WHEN c.not_after < (CURRENT_TIMESTAMP + INTERVAL '30 days') THEN 'warning'
        ELSE 'valid'
    END AS expiry_status,

    -- File paths for easy access
    c.certificate_path,
    c.private_key_path,
    c.fullchain_path,

    -- Renewal information
    (SELECT COUNT(*) FROM unified.certificate_renewals cr
     WHERE cr.certificate_id = c.id AND cr.success = false
     AND cr.created_at > CURRENT_TIMESTAMP - INTERVAL '30 days') AS recent_failed_renewals

FROM unified.certificates c
WHERE c.is_active = true
ORDER BY c.not_after ASC;

-- Certificate files with integrity status
CREATE VIEW unified.certificate_file_status AS
SELECT
    c.domain,
    c.certificate_type,
    cf.file_type,
    cf.file_path,
    cf.file_size,
    cf.file_checksum,
    cf.file_permissions,
    cf.last_verified,
    (CURRENT_TIMESTAMP - cf.last_verified) AS time_since_verification,
    CASE
        WHEN cf.last_verified < (CURRENT_TIMESTAMP - INTERVAL '24 hours') THEN 'needs_verification'
        ELSE 'verified'
    END AS verification_status
FROM unified.certificates c
JOIN unified.certificate_files cf ON c.id = cf.certificate_id
WHERE c.is_active = true
ORDER BY c.domain, cf.file_type;

-- ================================================================
-- CERTIFICATE MANAGEMENT FUNCTIONS
-- ================================================================

-- Function to update certificate updated_at timestamp
CREATE OR REPLACE FUNCTION unified.update_certificate_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to automatically update certificate timestamps
CREATE TRIGGER trigger_certificates_updated_at
    BEFORE UPDATE ON unified.certificates
    FOR EACH ROW
    EXECUTE FUNCTION unified.update_certificate_timestamp();

-- Function to send certificate notifications via LISTEN/NOTIFY
CREATE OR REPLACE FUNCTION unified.notify_certificate_change()
RETURNS TRIGGER AS $$
DECLARE
    notification_type VARCHAR(50);
    notification_data JSONB;
BEGIN
    -- Determine notification type
    IF TG_OP = 'INSERT' THEN
        notification_type = 'created';
    ELSIF TG_OP = 'UPDATE' THEN
        notification_type = 'updated';
    ELSIF TG_OP = 'DELETE' THEN
        notification_type = 'deleted';
    END IF;

    -- Prepare notification data
    notification_data = jsonb_build_object(
        'certificate_id', COALESCE(NEW.id, OLD.id),
        'domain', COALESCE(NEW.domain, OLD.domain),
        'certificate_type', COALESCE(NEW.certificate_type, OLD.certificate_type),
        'operation', TG_OP,
        'timestamp', CURRENT_TIMESTAMP
    );

    -- Insert notification record
    INSERT INTO unified.certificate_notifications (
        certificate_id,
        notification_type,
        message,
        data
    ) VALUES (
        COALESCE(NEW.id, OLD.id),
        notification_type,
        format('Certificate %s for domain %s', notification_type, COALESCE(NEW.domain, OLD.domain)),
        notification_data
    );

    -- Send PostgreSQL notification
    PERFORM pg_notify('certificate_changes', notification_data::text);

    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

-- Trigger for certificate change notifications
CREATE TRIGGER trigger_certificate_notifications
    AFTER INSERT OR UPDATE OR DELETE ON unified.certificates
    FOR EACH ROW
    EXECUTE FUNCTION unified.notify_certificate_change();

-- Function to check certificate expiration and schedule renewals
CREATE OR REPLACE FUNCTION unified.check_certificate_expiration()
RETURNS TABLE (
    certificate_id INTEGER,
    domain VARCHAR(255),
    days_until_expiry INTEGER,
    renewal_scheduled BOOLEAN
) AS $$
DECLARE
    cert_record RECORD;
    renewal_threshold INTEGER := 30; -- Start renewal process 30 days before expiration
BEGIN
    FOR cert_record IN
        SELECT id, domain, not_after, auto_renew, certificate_type
        FROM unified.certificates
        WHERE is_active = true AND auto_renew = true
    LOOP
        -- Calculate days until expiration
        days_until_expiry := EXTRACT(days FROM (cert_record.not_after - CURRENT_TIMESTAMP));

        -- Check if renewal is needed
        IF days_until_expiry <= renewal_threshold THEN
            -- Check if renewal is already scheduled
            IF NOT EXISTS (
                SELECT 1 FROM unified.certificate_renewals
                WHERE certificate_id = cert_record.id
                AND scheduled_at > CURRENT_TIMESTAMP
                AND completed_at IS NULL
            ) THEN
                -- Schedule renewal
                INSERT INTO unified.certificate_renewals (
                    certificate_id,
                    scheduled_at,
                    renewal_method,
                    triggered_by
                ) VALUES (
                    cert_record.id,
                    CURRENT_TIMESTAMP + INTERVAL '1 hour', -- Schedule for 1 hour from now
                    'automatic',
                    'expiration_check'
                );

                renewal_scheduled := true;
            ELSE
                renewal_scheduled := false;
            END IF;

            -- Return the record
            certificate_id := cert_record.id;
            domain := cert_record.domain;
            RETURN NEXT;
        END IF;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- ================================================================
-- INDEXES FOR PERFORMANCE
-- ================================================================

-- Certificate lookups
CREATE INDEX idx_certificates_domain ON unified.certificates(domain);
CREATE INDEX idx_certificates_type ON unified.certificates(certificate_type);
CREATE INDEX idx_certificates_active ON unified.certificates(is_active);
CREATE INDEX idx_certificates_expiry ON unified.certificates(not_after);
CREATE INDEX idx_certificates_auto_renew ON unified.certificates(auto_renew);

-- Certificate files
CREATE INDEX idx_certificate_files_cert_id ON unified.certificate_files(certificate_id);
CREATE INDEX idx_certificate_files_type ON unified.certificate_files(file_type);
CREATE INDEX idx_certificate_files_path ON unified.certificate_files(file_path);

-- Notifications
CREATE INDEX idx_certificate_notifications_cert_id ON unified.certificate_notifications(certificate_id);
CREATE INDEX idx_certificate_notifications_type ON unified.certificate_notifications(notification_type);
CREATE INDEX idx_certificate_notifications_created ON unified.certificate_notifications(created_at);
CREATE INDEX idx_certificate_notifications_processed ON unified.certificate_notifications(processed_at);

-- Renewals
CREATE INDEX idx_certificate_renewals_cert_id ON unified.certificate_renewals(certificate_id);
CREATE INDEX idx_certificate_renewals_scheduled ON unified.certificate_renewals(scheduled_at);
CREATE INDEX idx_certificate_renewals_success ON unified.certificate_renewals(success);
CREATE INDEX idx_certificate_renewals_created ON unified.certificate_renewals(created_at);

-- ================================================================
-- INITIAL CONFIGURATION
-- ================================================================

-- Grant permissions to application users
-- (These would be granted to specific application database users in production)

COMMENT ON TABLE unified.certificates IS 'Core certificate management table storing SSL/TLS certificate metadata and paths';
COMMENT ON TABLE unified.certificate_files IS 'Individual certificate files with integrity verification';
COMMENT ON TABLE unified.certificate_notifications IS 'Certificate change notifications for real-time updates';
COMMENT ON TABLE unified.certificate_renewals IS 'Certificate renewal scheduling and history';

COMMENT ON VIEW unified.certificate_status IS 'Active certificates with expiration status and file paths';
COMMENT ON VIEW unified.certificate_file_status IS 'Certificate files with integrity verification status';

COMMENT ON FUNCTION unified.check_certificate_expiration() IS 'Checks certificate expiration and schedules automatic renewals';

#!/bin/bash
set -e

# Apache entrypoint script for unified project
# Configures Apache with environment variables and templates

echo "Starting Apache container for unified project..."

# Default environment variables
export APACHE_RUN_USER=${APACHE_RUN_USER:-www-data}
export APACHE_RUN_GROUP=${APACHE_RUN_GROUP:-www-data}
export APACHE_PID_FILE=${APACHE_PID_FILE:-/var/run/apache2/apache2.pid}
export APACHE_RUN_DIR=${APACHE_RUN_DIR:-/var/run/apache2}
export APACHE_LOCK_DIR=${APACHE_LOCK_DIR:-/var/lock/apache2}
export APACHE_LOG_DIR=${APACHE_LOG_DIR:-/var/log/apache2}

# Unified project specific variables
export UNIFIED_DB_HOST=${UNIFIED_DB_HOST:-localhost}
export UNIFIED_DB_PORT=${UNIFIED_DB_PORT:-5435}
export UNIFIED_DB_NAME=${UNIFIED_DB_NAME:-poststack}
export UNIFIED_DB_USER=${UNIFIED_DB_USER:-poststack}
export UNIFIED_DB_PASSWORD=${UNIFIED_DB_PASSWORD:-poststack_dev}
export UNIFIED_DB_SCHEMA=${UNIFIED_DB_SCHEMA:-unified}

# Create run directory
mkdir -p $APACHE_RUN_DIR

# Process configuration templates
echo "Processing Apache configuration templates..."

# Replace placeholders in apache2.conf
envsubst < /etc/apache2/apache2.conf.template > /etc/apache2/apache2.conf

# Replace placeholders in site configuration
envsubst < /etc/apache2/sites-available/unified.conf.template > /etc/apache2/sites-available/unified.conf

# Enable the unified site
a2ensite unified
a2dissite 000-default

# Create a simple health check endpoint
mkdir -p /var/www/unified
cat > /var/www/unified/health.php << 'EOF'
<?php
header('Content-Type: application/json');
echo json_encode([
    'status' => 'healthy',
    'service' => 'unified-apache',
    'timestamp' => date('c'),
    'database' => [
        'host' => $_ENV['UNIFIED_DB_HOST'] ?? 'localhost',
        'port' => $_ENV['UNIFIED_DB_PORT'] ?? '5435',
        'schema' => $_ENV['UNIFIED_DB_SCHEMA'] ?? 'unified'
    ]
]);
?>
EOF

# Create a simple index page
cat > /var/www/unified/index.php << 'EOF'
<!DOCTYPE html>
<html>
<head>
    <title>Unified Project</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        .container { max-width: 800px; margin: 0 auto; }
        .status { background: #e8f5e8; padding: 20px; border-radius: 5px; margin: 20px 0; }
        .info { background: #f0f8ff; padding: 15px; border-radius: 5px; margin: 10px 0; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 Unified Project</h1>
        <p>Apache web server running with poststack PostgreSQL backend</p>

        <div class="status">
            <h3>✅ System Status</h3>
            <p><strong>Server:</strong> Apache/<?= apache_get_version() ?></p>
            <p><strong>PHP:</strong> <?= phpversion() ?></p>
            <p><strong>Time:</strong> <?= date('Y-m-d H:i:s T') ?></p>
        </div>

        <div class="info">
            <h3>🗄️ Database Configuration</h3>
            <p><strong>Host:</strong> <?= $_ENV['UNIFIED_DB_HOST'] ?? 'localhost' ?></p>
            <p><strong>Port:</strong> <?= $_ENV['UNIFIED_DB_PORT'] ?? '5435' ?></p>
            <p><strong>Database:</strong> <?= $_ENV['UNIFIED_DB_NAME'] ?? 'poststack' ?></p>
            <p><strong>Schema:</strong> <?= $_ENV['UNIFIED_DB_SCHEMA'] ?? 'unified' ?></p>
        </div>

        <div class="info">
            <h3>🔗 Quick Links</h3>
            <p><a href="/health">Health Check</a></p>
            <p><a href="/users">User Management</a> (coming soon)</p>
        </div>
    </div>
</body>
</html>
EOF

# Set proper permissions
chown -R www-data:www-data /var/www/unified

echo "Apache configuration complete. Starting server..."

# Execute the command passed to docker run
exec "$@"

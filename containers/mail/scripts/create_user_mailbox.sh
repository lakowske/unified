#!/bin/bash
# Individual mailbox creation script for unified project
# Creates a mailbox for a specific user

set -e

# Check arguments
if [ $# -ne 1 ]; then
    echo "Usage: $0 <email_address>"
    echo "Example: $0 user@example.com"
    exit 1
fi

EMAIL="$1"
USERNAME=$(echo "$EMAIL" | cut -d'@' -f1)
DOMAIN=$(echo "$EMAIL" | cut -d'@' -f2)

echo "Creating mailbox for $EMAIL..."

# Database connection check
if [ -z "$DB_HOST" ] || [ -z "$DB_PORT" ] || [ -z "$DB_NAME" ] || [ -z "$DB_USER" ]; then
    echo "ERROR: Database connection variables not set"
    echo "Required: DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD"
    exit 1
fi

# Query specific user's mailbox information
QUERY="SELECT username, domain, home FROM unified.dovecot_users WHERE \"user\" = '$EMAIL' AND home IS NOT NULL;"

echo "Querying database for user $EMAIL..."
RESULT=$(PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
    -t -c "$QUERY" | xargs)

if [ -z "$RESULT" ]; then
    echo "ERROR: User $EMAIL not found in database or has no home directory configured"
    exit 1
fi

# Parse result
IFS='|' read -r db_username db_domain home_dir <<< "$RESULT"
db_username=$(echo "$db_username" | xargs)
db_domain=$(echo "$db_domain" | xargs)
home_dir=$(echo "$home_dir" | xargs)

echo "Found user: $db_username@$db_domain"
echo "Home directory: $home_dir"

# Create mailbox directory structure
echo "Creating mailbox structure..."

# Main mailbox directories
mkdir -p "$home_dir"/{cur,new,tmp}

# Set proper ownership and permissions
chown -R vmail:vmail "$home_dir"
chmod -R 750 "$home_dir"

# Create Maildir marker file
touch "$home_dir/maildirfolder"

# Create standard IMAP folders
echo "Creating standard folders..."
for folder in Drafts Sent Trash Junk; do
    folder_path="$home_dir/.$folder"
    mkdir -p "$folder_path"/{cur,new,tmp}
    chown -R vmail:vmail "$folder_path"
    chmod -R 750 "$folder_path"
    touch "$folder_path/maildirfolder"
    echo "  Created folder: $folder"
done

# Create dovecot-uidlist file for IMAP UID tracking
touch "$home_dir/dovecot-uidlist"
chown vmail:vmail "$home_dir/dovecot-uidlist"
chmod 600 "$home_dir/dovecot-uidlist"

# Create subscriptions file for default folder subscriptions
cat > "$home_dir/subscriptions" << EOF
INBOX
Drafts
Sent
Trash
Junk
EOF
chown vmail:vmail "$home_dir/subscriptions"
chmod 600 "$home_dir/subscriptions"

echo "Mailbox created successfully for $EMAIL at $home_dir"
echo "Standard folders: INBOX, Drafts, Sent, Trash, Junk"

#!/bin/bash
# Bulk mailbox creation script for unified project
# Creates mailboxes for all active users in the database

set -e

echo "Creating mailboxes for all active users..."

# Database connection check
if [ -z "$DB_HOST" ] || [ -z "$DB_PORT" ] || [ -z "$DB_NAME" ] || [ -z "$DB_USER" ]; then
    echo "ERROR: Database connection variables not set"
    echo "Required: DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD"
    exit 1
fi

# Query all active users with email access
QUERY="SELECT username, domain, home FROM unified.dovecot_users WHERE home IS NOT NULL ORDER BY domain, username;"

echo "Querying database for users..."
PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
    -t -c "$QUERY" | while IFS='|' read -r username domain home_dir; do

    # Trim whitespace
    username=$(echo "$username" | xargs)
    domain=$(echo "$domain" | xargs)
    home_dir=$(echo "$home_dir" | xargs)

    if [ -n "$username" ] && [ -n "$domain" ] && [ -n "$home_dir" ]; then
        echo "Creating mailbox for $username@$domain at $home_dir"

        # Create directory structure
        mkdir -p "$home_dir"/{cur,new,tmp}

        # Set proper ownership and permissions
        chown -R vmail:vmail "$home_dir"
        chmod -R 750 "$home_dir"

        # Create Maildir structure files
        touch "$home_dir/maildirfolder"

        # Create standard folders
        for folder in Drafts Sent Trash Junk; do
            folder_path="$home_dir/.$folder"
            mkdir -p "$folder_path"/{cur,new,tmp}
            chown -R vmail:vmail "$folder_path"
            chmod -R 750 "$folder_path"
            touch "$folder_path/maildirfolder"
        done

        echo "  Mailbox created successfully for $username@$domain"
    fi
done

echo "Bulk mailbox creation completed"

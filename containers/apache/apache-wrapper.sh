#!/bin/bash

# Signal-forwarding wrapper for Apache
# Ensures Apache receives proper SIGTERM for graceful shutdown

set -e

# PID file for tracking Apache process
APACHE_PID=""

# Signal handler for graceful shutdown
shutdown_handler() {
    echo "Received shutdown signal, stopping Apache gracefully..."
    if [ -n "$APACHE_PID" ] && kill -0 "$APACHE_PID" 2>/dev/null; then
        echo "Sending SIGTERM to Apache (PID: $APACHE_PID)"
        kill -TERM "$APACHE_PID"

        # Wait for Apache to shutdown gracefully (max 30 seconds)
        local count=0
        while [ $count -lt 30 ] && kill -0 "$APACHE_PID" 2>/dev/null; do
            sleep 1
            count=$((count + 1))
        done

        # Force kill if still running
        if kill -0 "$APACHE_PID" 2>/dev/null; then
            echo "Apache didn't shutdown gracefully, sending SIGKILL"
            kill -KILL "$APACHE_PID"
        else
            echo "Apache shutdown gracefully"
        fi
    fi
    exit 0
}

# Set up signal handlers
trap shutdown_handler SIGTERM SIGINT

echo "Starting Apache with signal forwarding..."

# Start Apache in the background
/usr/sbin/apache2 -D FOREGROUND &
APACHE_PID=$!

echo "Apache started with PID: $APACHE_PID"

# Wait for Apache to exit
wait $APACHE_PID
echo "Apache process exited"

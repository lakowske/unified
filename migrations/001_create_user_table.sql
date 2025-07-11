-- Create user table migration
-- This creates a simple users table with basic fields

-- Create the unified schema if it doesn't exist
CREATE SCHEMA IF NOT EXISTS unified;

CREATE TABLE unified.users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(255) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index on email for faster lookups
CREATE INDEX idx_users_email ON unified.users(email);

-- Create index on username for faster lookups
CREATE INDEX idx_users_username ON unified.users(username);

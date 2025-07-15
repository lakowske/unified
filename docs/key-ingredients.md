A document containing key elements of a network server system.

# Template engine

Splicing together configuration, Jinja provides a parsimonious read through conditional configuration.

# Interface

A CLI provides entrypoints into functionality, orchestration and common actions.

# Rendering configuration

Create a dry run to debug configuration rendering.  Create start/stop/restart/rm operations

# Init container

Provision filesystem volumes with a shared directory structure and permissions for server processes.

# Database

Provides a way to update system data (configuration, users, etc...) efficiently (inserts, updates, delete, create).

# Web server

Run remote operations. A network protocol for requesting encryption certificates.

# Mail server

Notify and message users of the system.

## DKIM

Sign emails with a digital signature

## DMARC

Instructions to follow after checking SPF and DKIM.

## SPF

A list of ip addresses of all the server allowed to send emails from the domain.

# Encryption

Ensures operations and credentials are not leaked in transport across network.

# Fail2Ban

Keep intruders and pests off the server stack.

# DNS server

Resolve server names to ip addresses.  Email server credentials, encryption and improved deliverability.

## Reverse DNS

Make or break for email deliverability

# Testing

Per container tests validating functionality.

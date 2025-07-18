# Unified Infrastructure Makefile
# Manages container builds with proper dependencies

# Configuration
DOCKER := docker
PROJECT := unified
BASE_IMAGE := localhost/$(PROJECT)/base-debian:latest
POSTGRES_IMAGE := localhost/$(PROJECT)/postgres:latest
VOLUME_SETUP_IMAGE := localhost/$(PROJECT)/volume-setup:latest
APACHE_IMAGE := localhost/$(PROJECT)/apache:latest
MAIL_IMAGE := localhost/$(PROJECT)/mail:latest
DNS_IMAGE := localhost/$(PROJECT)/dns:latest

# Timestamp files for dependency tracking
BUILD_DIR := .build
BASE_STAMP := $(BUILD_DIR)/base-debian.stamp
POSTGRES_STAMP := $(BUILD_DIR)/postgres.stamp
VOLUME_SETUP_STAMP := $(BUILD_DIR)/volume-setup.stamp
APACHE_STAMP := $(BUILD_DIR)/apache.stamp
MAIL_STAMP := $(BUILD_DIR)/mail.stamp
DNS_STAMP := $(BUILD_DIR)/dns.stamp

# Source file dependencies
BASE_SOURCES := containers/base-debian/Dockerfile
POSTGRES_SOURCES := containers/postgres/Dockerfile containers/postgres/entrypoint.sh containers/postgres/postgresql.conf.template containers/postgres/pg_hba.conf.template
VOLUME_SETUP_SOURCES := containers/volume-setup/Dockerfile containers/volume-setup/setup-volumes.sh containers/volume-setup/uid-mapping.sh
APACHE_SOURCES := containers/apache/Dockerfile containers/apache/entrypoint.sh containers/apache/apache2.conf.template containers/apache/sites-available/unified.conf.template containers/apache/sites-available/unified-ssl.conf.template containers/apache/generate-certificate.sh
MAIL_SOURCES := containers/mail/Dockerfile containers/mail/entrypoint.sh containers/mail/dovecot.conf.template containers/mail/dovecot-sql.conf.template containers/mail/postfix/main.cf.template containers/mail/postfix/master.cf.template containers/mail/opendkim/opendkim.conf.template containers/mail/opendkim/key.table.template containers/mail/opendkim/signing.table.template containers/mail/opendkim/trusted.hosts.template containers/mail/generate-dkim-keys.sh containers/mail/configure-ssl.sh containers/mail/reload-ssl.sh containers/mail/certificate-watcher.py containers/mail/scripts/create_mailboxes.sh containers/mail/scripts/create_user_mailbox.sh containers/mail/scripts/mailbox-listener.py
DNS_SOURCES := containers/dns/Dockerfile containers/dns/entrypoint.sh containers/dns/named.conf containers/dns/named.conf.options containers/dns/named.conf.local containers/dns/manage-dkim-records.py containers/dns/zones/mail-domain.zone.template containers/dns/zones/rpz.zone

# Default target
.PHONY: all
all: $(BASE_STAMP) $(POSTGRES_STAMP) $(VOLUME_SETUP_STAMP) $(APACHE_STAMP) $(MAIL_STAMP) $(DNS_STAMP)

# Base image - foundation for all others
$(BASE_STAMP): $(BASE_SOURCES) | $(BUILD_DIR)
	@echo "Building base-debian image..."
	$(DOCKER) build -f containers/base-debian/Dockerfile . -t $(BASE_IMAGE)
	@touch $@

# PostgreSQL image depends on base
$(POSTGRES_STAMP): $(BASE_STAMP) $(POSTGRES_SOURCES) | $(BUILD_DIR)
	@echo "Building postgres image..."
	$(DOCKER) build -f containers/postgres/Dockerfile . -t $(POSTGRES_IMAGE)
	@touch $@

# Volume setup image depends on base
$(VOLUME_SETUP_STAMP): $(BASE_STAMP) $(VOLUME_SETUP_SOURCES) | $(BUILD_DIR)
	@echo "Building volume-setup image..."
	$(DOCKER) build -f containers/volume-setup/Dockerfile . -t $(VOLUME_SETUP_IMAGE)
	@touch $@

# Apache image depends on base
$(APACHE_STAMP): $(BASE_STAMP) $(APACHE_SOURCES) | $(BUILD_DIR)
	@echo "Building apache image..."
	$(DOCKER) build -f containers/apache/Dockerfile . -t $(APACHE_IMAGE)
	@touch $@

# Mail image depends on base
$(MAIL_STAMP): $(BASE_STAMP) $(MAIL_SOURCES) | $(BUILD_DIR)
	@echo "Building mail image..."
	$(DOCKER) build -f containers/mail/Dockerfile . -t $(MAIL_IMAGE)
	@touch $@

# DNS image depends on base
$(DNS_STAMP): $(BASE_STAMP) $(DNS_SOURCES) | $(BUILD_DIR)
	@echo "Building dns image..."
	$(DOCKER) build -f containers/dns/Dockerfile . -t $(DNS_IMAGE)
	@touch $@

# Create build directory
$(BUILD_DIR):
	@mkdir -p $(BUILD_DIR)

# Individual build targets
.PHONY: base-debian postgres volume-setup apache mail dns
base-debian: $(BASE_STAMP)
postgres: $(POSTGRES_STAMP)
volume-setup: $(VOLUME_SETUP_STAMP)
apache: $(APACHE_STAMP)
mail: $(MAIL_STAMP)
dns: $(DNS_STAMP)

# Environment management
.PHONY: up down restart logs status
up: all
	@echo "Starting development environment..."
	$(DOCKER) compose --env-file .env.dev -f docker-compose.yml -f docker-compose.dev.yml up -d

down:
	@echo "Stopping development environment..."
	$(DOCKER) compose --env-file .env.dev -f docker-compose.yml -f docker-compose.dev.yml down

restart: down up

logs:
	@echo "Viewing logs..."
	$(DOCKER) compose --env-file .env.dev -f docker-compose.yml -f docker-compose.dev.yml logs -f

status:
	@echo "Checking service status..."
	$(DOCKER) compose --env-file .env.dev -f docker-compose.yml -f docker-compose.dev.yml ps

# Cleanup targets
.PHONY: clean clean-images clean-volumes clean-all
clean:
	@echo "Removing build artifacts..."
	-rm -f $(BASE_STAMP) $(POSTGRES_STAMP) $(VOLUME_SETUP_STAMP) $(APACHE_STAMP) $(MAIL_STAMP) $(DNS_STAMP)
	-rmdir $(BUILD_DIR) 2>/dev/null || true

clean-images:
	@echo "Removing all unified images..."
	-$(DOCKER) rmi $$($(DOCKER) images --filter "reference=localhost/$(PROJECT)/*" -q) 2>/dev/null || true

clean-volumes:
	@echo "Removing development volumes..."
	-$(DOCKER) compose --env-file .env.dev -f docker-compose.yml -f docker-compose.dev.yml down -v

clean-all: down clean-volumes clean-images clean
	@echo "Complete cleanup finished"

# Rebuild targets
.PHONY: rebuild rebuild-base rebuild-postgres rebuild-apache rebuild-mail rebuild-dns
rebuild: clean-images all

rebuild-base: 
	-$(DOCKER) rmi $(BASE_IMAGE) 2>/dev/null || true
	rm -f $(BASE_STAMP)
	$(MAKE) $(BASE_STAMP)

rebuild-postgres:
	-$(DOCKER) rmi $(POSTGRES_IMAGE) 2>/dev/null || true
	rm -f $(POSTGRES_STAMP)
	$(MAKE) $(POSTGRES_STAMP)

rebuild-apache:
	-$(DOCKER) rmi $(APACHE_IMAGE) 2>/dev/null || true
	rm -f $(APACHE_STAMP)
	$(MAKE) $(APACHE_STAMP)

rebuild-mail:
	-$(DOCKER) rmi $(MAIL_IMAGE) 2>/dev/null || true
	rm -f $(MAIL_STAMP)
	$(MAKE) $(MAIL_STAMP)

rebuild-dns:
	-$(DOCKER) rmi $(DNS_IMAGE) 2>/dev/null || true
	rm -f $(DNS_STAMP)
	$(MAKE) $(DNS_STAMP)

# Help target
.PHONY: help
help:
	@echo "Unified Infrastructure Makefile"
	@echo ""
	@echo "Build targets:"
	@echo "  all            - Build all images"
	@echo "  base-debian    - Build base Debian image"
	@echo "  postgres       - Build PostgreSQL image"
	@echo "  volume-setup   - Build volume setup image"
	@echo "  apache         - Build Apache image"
	@echo "  mail           - Build mail server image"
	@echo "  dns            - Build DNS server image"
	@echo ""
	@echo "Environment management:"
	@echo "  up             - Start development environment"
	@echo "  down           - Stop development environment"
	@echo "  restart        - Restart development environment"
	@echo "  logs           - View container logs"
	@echo "  status         - Check service status"
	@echo ""
	@echo "Cleanup targets:"
	@echo "  clean          - Remove build artifacts"
	@echo "  clean-images   - Remove all unified images"
	@echo "  clean-volumes  - Remove development volumes"
	@echo "  clean-all      - Complete cleanup"
	@echo ""
	@echo "Rebuild targets:"
	@echo "  rebuild        - Rebuild all images"
	@echo "  rebuild-base   - Rebuild base image"
	@echo "  rebuild-*      - Rebuild specific image"
	@echo ""
	@echo "Note: Images are built with proper dependencies."
	@echo "      Changes to base-debian will trigger rebuilds of dependent images."
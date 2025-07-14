# TODO: Fix Database Migration Documentation and Commands

## Problem
The CLAUDE.md file contains incorrect migration commands that I added based on assumptions rather than the actual poststack CLI interface. The commands listed don't exist and need to be corrected.

## Current Issues
1. **Incorrect migration commands in CLAUDE.md**: Added fictional commands like:
   - `poststack migrate apply`
   - `poststack migrate apply 002`
   - `poststack migrate status`
   - `poststack migrate rollback`
   - `poststack migrate create <name>`

2. **Migration 002 was applied manually**: Used `poststack db shell` workaround instead of proper migration system

## Plan to Fix

### Phase 1: Discover Actual Poststack Commands
- [ ] Run `source .venv/bin/activate && poststack --help` to see all available commands
- [ ] Run `poststack db --help` to see all database subcommands  
- [ ] Document the actual migration-related commands available
- [ ] Test each command to understand proper usage patterns

### Phase 2: Update Documentation
- [ ] Remove incorrect migration commands from CLAUDE.md
- [ ] Add correct poststack migration commands with proper syntax
- [ ] Include examples of actual working commands
- [ ] Add notes about current limitations or workarounds if needed

### Phase 3: Test Migration Workflow
- [ ] Test the proper migration workflow with a new test migration
- [ ] Verify that `poststack db migrate-project` works correctly for new migrations
- [ ] Document any gotchas or special procedures needed

### Phase 4: Update Migration 002 Status
- [ ] Investigate how to properly mark migration 002 as applied in the poststack system
- [ ] Ensure migration tracking is consistent with what was actually applied

## Acceptance Criteria
- [ ] CLAUDE.md contains only real, tested poststack commands
- [ ] Migration commands work as documented
- [ ] Future developers can follow the documentation successfully
- [ ] Migration 002 is properly tracked in the migration system

## Priority
High - This affects developer experience and could cause confusion for anyone following the documentation.
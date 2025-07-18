#!/bin/bash
#
# Container Build Wrapper Script
#
# Simple wrapper around the Python parallel build system.
# Provides easy command-line interface for building containers.
#
# Usage:
#   ./scripts/build.sh                    # Build all containers
#   ./scripts/build.sh --help             # Show detailed help
#   ./scripts/build.sh --check            # Check dependencies only
#

set -e

# Change to project root directory
cd "$(dirname "$0")/.."

# Ensure logs directory exists
mkdir -p logs

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🏗️  Unified Infrastructure Container Build System${NC}"
echo -e "${BLUE}=================================================${NC}"

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Error: python3 is required but not found${NC}"
    echo "Please install Python 3.7+ to use the build system"
    exit 1
fi

# Check if docker is available
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Error: docker is required but not found${NC}"
    echo "Please install Docker to build containers"
    exit 1
fi

# Handle command line arguments
case "${1:-}" in
    --help|-h)
        echo "Container Build System Help"
        echo ""
        echo "Usage:"
        echo "  ./scripts/build.sh                 Build all containers in parallel"
        echo "  ./scripts/build.sh --help          Show this help message"
        echo "  ./scripts/build.sh --check         Check build dependencies only"
        echo ""
        echo "Features:"
        echo "  ✅ Parallel building with dependency management"
        echo "  ✅ Comprehensive build logging to logs/ directory"
        echo "  ✅ Build timing and performance metrics"
        echo "  ✅ Shared base image efficiency"
        echo "  ✅ Error handling and recovery"
        echo ""
        echo "Build order:"
        echo "  1. base-debian (shared base image)"
        echo "  2. postgres, volume-setup, apache, mail, dns (parallel)"
        echo ""
        echo "Logs:"
        echo "  - Build logs: logs/build-{container}-{timestamp}.log"
        echo "  - Summary: logs/build-summary-{timestamp}.json"
        echo "  - System log: logs/container-build-{timestamp}.log"
        exit 0
        ;;
    --check)
        echo -e "${YELLOW}🔍 Checking build dependencies...${NC}"
        python3 -c "
import sys
from pathlib import Path

# Check required files exist
dockerfiles = [
    '/home/seth/Software/dev/unified/containers/base-debian/Dockerfile',
    '/home/seth/Software/dev/unified/containers/postgres/Dockerfile',
    '/home/seth/Software/dev/unified/containers/volume-setup/Dockerfile',
    '/home/seth/Software/dev/unified/containers/apache/Dockerfile',
    '/home/seth/Software/dev/unified/containers/mail/Dockerfile',
    '/home/seth/Software/dev/unified/containers/dns/Dockerfile'
]

missing = []
for dockerfile in dockerfiles:
    if not Path(dockerfile).exists():
        missing.append(dockerfile)

if missing:
    print('❌ Missing Dockerfiles:')
    for f in missing:
        print(f'  - {f}')
    sys.exit(1)
else:
    print('✅ All Dockerfiles found')
    print('✅ Build dependencies check passed')
"
        exit $?
        ;;
    "")
        # Default: run the build
        echo -e "${GREEN}🚀 Starting parallel container build...${NC}"
        echo ""
        ;;
    *)
        echo -e "${RED}❌ Unknown option: $1${NC}"
        echo "Use --help for usage information"
        exit 1
        ;;
esac

# Execute the Python build system
echo -e "${BLUE}Executing: python3 scripts/build-containers.py${NC}"
echo ""

exec python3 scripts/build-containers.py

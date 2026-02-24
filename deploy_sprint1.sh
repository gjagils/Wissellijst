#!/bin/bash

# Sprint 1 Deployment Script
# This script automates the deployment of Sprint 1 changes

set -e  # Exit on any error

echo "============================================================"
echo "SPRINT 1 DEPLOYMENT SCRIPT"
echo "============================================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print success message
success() {
    echo -e "${GREEN}✓${NC} $1"
}

# Function to print error message
error() {
    echo -e "${RED}✗${NC} $1"
}

# Function to print warning message
warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# Function to print step
step() {
    echo -e "\n${YELLOW}==>${NC} $1"
}

# Check if docker compose is available
step "Checking prerequisites..."
if ! command -v docker &> /dev/null; then
    error "Docker not found. Please install Docker first."
    exit 1
fi
success "Docker is installed"

if docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
    success "Docker Compose (v2) is available"
elif command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
    success "Docker Compose (v1) is available"
else
    error "Docker Compose not found. Please install Docker Compose."
    exit 1
fi

# Check if .env file exists
if [ ! -f ".env" ]; then
    warning ".env file not found!"
    echo "Please create a .env file with the following variables:"
    echo "  SPOTIFY_CLIENT_ID=..."
    echo "  SPOTIFY_CLIENT_SECRET=..."
    echo "  SPOTIFY_REDIRECT_URI=..."
    echo "  OPENAI_API_KEY=..."
    echo "  DATABASE_URL=postgresql://playlist:playlist@db:5432/playlistdb"
    exit 1
fi
success ".env file found"

# Stop containers
step "Stopping existing containers..."
$COMPOSE_CMD down
success "Containers stopped"

# Build and start containers
step "Building and starting containers..."
$COMPOSE_CMD up -d --build
success "Containers started"

# Wait for database to be ready
step "Waiting for database to be ready..."
sleep 10

# Check if containers are running
if ! $COMPOSE_CMD ps | grep -q "Up"; then
    error "Containers failed to start. Check logs with: $COMPOSE_CMD logs"
    exit 1
fi
success "Containers are running"

# Run database migration
step "Running database migration..."
if $COMPOSE_CMD exec -T app alembic upgrade head; then
    success "Migration completed successfully"
else
    error "Migration failed. Check logs with: $COMPOSE_CMD logs app"
    exit 1
fi

# Verify migration
step "Verifying migration..."
MIGRATION_VERSION=$($COMPOSE_CMD exec -T app alembic current 2>/dev/null | grep -o 'ac11471a3939' || echo "")
if [ "$MIGRATION_VERSION" = "ac11471a3939" ]; then
    success "Migration version verified: ac11471a3939"
else
    warning "Migration version could not be verified. Please check manually."
fi

# Run tests
step "Running validation tests..."
if $COMPOSE_CMD exec -T app python -m tests.test_validators 2>&1 | grep -q "TEST SUITE COMPLETED"; then
    success "PolicyValidator tests completed"
else
    warning "PolicyValidator tests may have issues. Review output above."
fi

step "Running metadata service tests..."
if $COMPOSE_CMD exec -T app python -m tests.test_metadata_service 2>&1 | grep -q "ALL TESTS PASSED"; then
    success "MetadataService tests passed"
else
    warning "MetadataService tests may have issues. Review output above."
fi

# Check API health
step "Checking API health..."
sleep 5
if curl -s http://localhost:8000/health | grep -q "healthy"; then
    success "API is healthy"
else
    warning "API health check failed. The API might not be fully started yet."
    echo "   Try: curl http://localhost:8000/health"
fi

# Final summary
echo ""
echo "============================================================"
echo "DEPLOYMENT SUMMARY"
echo "============================================================"
echo ""
success "Sprint 1 deployment completed!"
echo ""
echo "Next steps:"
echo "  1. Verify migration: $COMPOSE_CMD exec app alembic current"
echo "  2. Check logs: $COMPOSE_CMD logs -f app"
echo "  3. Test API: curl http://localhost:8000/health"
echo "  4. Run SQL verification: $COMPOSE_CMD exec -T db psql -U playlist -d playlistdb < app/verify_migration.sql"
echo ""
echo "Useful commands:"
echo "  View logs: $COMPOSE_CMD logs -f app"
echo "  Restart: $COMPOSE_CMD restart app"
echo "  Stop: $COMPOSE_CMD down"
echo "  Shell: $COMPOSE_CMD exec app bash"
echo ""
echo "Troubleshooting:"
echo "  See DEPLOYMENT_GUIDE.md for detailed troubleshooting steps"
echo ""
echo "============================================================"

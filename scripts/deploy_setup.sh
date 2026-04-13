#!/bin/bash
# Deployment setup script for AWS Elastic Beanstalk
# Run this locally before deploying to ensure everything is configured

set -e

echo "=== TenantGuard AWS EBS Deployment Setup ==="

# Check required environment variables
REQUIRED_VARS=("AWS_ACCESS_KEY_ID" "AWS_SECRET_ACCESS_KEY" "AWS_EB_BUCKET" "DJANGO_SECRET_KEY")

for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var}" ]; then
        echo "ERROR: $var is not set"
        echo "Please set it in Travis CI environment variables"
        exit 1
    fi
done

echo "✓ All required environment variables are set"

# Validate .ebextensions
if [ ! -d ".ebextensions" ]; then
    echo "ERROR: .ebextensions directory not found"
    exit 1
fi

echo "✓ .ebextensions directory exists"

# Check if requirements.txt exists
if [ ! -f "requirements.txt" ]; then
    echo "ERROR: requirements.txt not found"
    exit 1
fi

echo "✓ requirements.txt found"

# Run tests
echo "Running tests..."
python manage.py test

echo "✓ All tests passed"

# Check linting
echo "Checking code style..."
black --check .
flake8 .

echo "✓ Code style checks passed"

echo ""
echo "=== Deployment Checklist ==="
echo "1. Ensure AWS credentials are set in Travis CI"
echo "2. Update .travis.yml with correct EB app and environment names"
echo "3. Set production environment variables in EB console:"
echo "   - DJANGO_SECRET_KEY (strong random key)"
echo "   - DEBUG=False"
echo "   - ALLOWED_HOSTS (your EB domain)"
echo "   - DATABASE_URL (RDS connection string)"
echo "   - NYC_OPEN_DATA_APP_TOKEN (optional, for API rate limits)"
echo "4. Configure RDS PostgreSQL database with PostGIS extension"
echo "5. Push to main or develop branch to trigger deployment"
echo ""
echo "Ready to deploy!"

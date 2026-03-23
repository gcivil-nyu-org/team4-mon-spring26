#!/bin/bash
# Post-deployment hook for AWS Elastic Beanstalk
# This runs after the application is deployed

set -e

# Activate virtual environment
source /var/app/venv/*/bin/activate
cd /var/app/current

# Log file
LOG_FILE="/var/log/eb-postdeploy.log"

echo "$(date): Starting post-deployment data setup" >> $LOG_FILE

# Run migrations (should already be done, but just in case)
python manage.py migrate --noinput >> $LOG_FILE 2>&1

# Check if this is first deployment (no data yet)
DATA_EXISTS=$(python manage.py shell -c "from mapview.models import NTARiskScore; print(NTARiskScore.objects.exists())" 2>/dev/null || echo "False")

if [ "$DATA_EXISTS" = "False" ]; then
    echo "$(date): First deployment detected, ingesting initial data..." >> $LOG_FILE
    python manage.py ingest_all --limit 2000 >> $LOG_FILE 2>&1 || echo "$(date): Data ingestion failed (non-critical)" >> $LOG_FILE
else
    echo "$(date): Data already exists, skipping initial ingestion" >> $LOG_FILE
fi

echo "$(date): Post-deployment setup complete" >> $LOG_FILE

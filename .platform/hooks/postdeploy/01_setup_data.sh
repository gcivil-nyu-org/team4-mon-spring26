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

# Check if NTA data exists
NTA_COUNT=$(python manage.py shell -c "from mapview.models import NTARiskScore; print(NTARiskScore.objects.count())" 2>/dev/null || echo "0")

if [ "$NTA_COUNT" -gt "0" ]; then
    echo "$(date): NTA data exists ($NTA_COUNT records), creating communities..." >> $LOG_FILE
    python manage.py create_nta_communities >> $LOG_FILE 2>&1
    python manage.py assign_user_communities >> $LOG_FILE 2>&1
else
    echo "$(date): No NTA data yet, skipping community creation (run create_nta_communities manually after data ingestion)" >> $LOG_FILE
fi

echo "$(date): Post-deployment setup complete" >> $LOG_FILE

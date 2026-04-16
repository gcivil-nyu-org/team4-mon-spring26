#!/bin/bash
# Post-deployment hook for AWS Elastic Beanstalk
# This runs after the application is deployed

set -e

# Activate virtual environment
source /var/app/venv/*/bin/activate
cd /var/app/current

# Log file
LOG_FILE="/var/log/eb-postdeploy.log"
SETUP_MARKER="/tmp/tenantguard-community-setup-done"

echo "$(date): Starting post-deployment setup" >> $LOG_FILE

# Run migrations (fast, always needed)
python manage.py migrate --noinput >> $LOG_FILE 2>&1

echo "$(date): Migrations complete" >> $LOG_FILE

# Collect static files (fast, ensures UI works after deployment)
python manage.py collectstatic --noinput >> $LOG_FILE 2>&1

echo "$(date): Static files collected" >> $LOG_FILE

# Only run community setup once (marker file approach to avoid DB queries)
# This avoids overhead on frequent deployments
if [ ! -f "$SETUP_MARKER" ]; then
    echo "$(date): First deployment detected, running community setup in background..." >> $LOG_FILE
    nohup bash -c "
        sleep 5
        python manage.py create_nta_communities >> $LOG_FILE 2>&1 && \
        python manage.py assign_user_communities >> $LOG_FILE 2>&1 && \
        touch $SETUP_MARKER && \
        echo \"\$(date): Background community setup complete\" >> $LOG_FILE
    " &
else
    echo "$(date): Community setup already completed, skipping" >> $LOG_FILE
fi

echo "$(date): Post-deployment setup complete" >> $LOG_FILE

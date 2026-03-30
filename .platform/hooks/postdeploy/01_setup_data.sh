#!/bin/bash
# Post-deployment hook for AWS Elastic Beanstalk
# This runs after the application is deployed

set -e

# Activate virtual environment
source /var/app/venv/*/bin/activate
cd /var/app/current

# Log file
LOG_FILE="/var/log/eb-postdeploy.log"

echo "$(date): Starting post-deployment setup" >> $LOG_FILE

# Run migrations
python manage.py migrate --noinput >> $LOG_FILE 2>&1

echo "$(date): Migrations complete" >> $LOG_FILE

# Run community setup in background to avoid timeout
# This will complete after deployment finishes
nohup bash -c "
    sleep 10
    python manage.py create_nta_communities >> $LOG_FILE 2>&1 || echo 'Community creation skipped or failed' >> $LOG_FILE
    python manage.py assign_user_communities >> $LOG_FILE 2>&1 || echo 'User assignment skipped or failed' >> $LOG_FILE
    echo \"\$(date): Background community setup complete\" >> $LOG_FILE
" &

echo "$(date): Post-deployment setup complete (community setup running in background)" >> $LOG_FILE

# AWS Elastic Beanstalk Deployment Guide

**Current source of truth:** [README.md](../README.md) (deploy steps, Travis, branch protection). This file is legacy detail; cron and postdeploy auto-ingest were removed for a simpler demo path—run `ingest_all` manually if needed.

## Prerequisites

1. **AWS Account** with appropriate permissions
2. **AWS CLI** installed and configured
3. **EB CLI** installed (`pip install awsebcli`)
4. **PostgreSQL RDS** instance with PostGIS extension
5. **Travis CI** configured for your repository

## Environment Setup

### 1. AWS RDS Database Setup

Create a PostgreSQL database with PostGIS:

```bash
# Connect to your RDS instance
psql -h your-rds-endpoint.rds.amazonaws.com -U postgres

# Enable PostGIS extension
CREATE EXTENSION postgis;
```

### 2. Travis CI Environment Variables

Configure these in Travis CI settings (Settings → Environment Variables):

```
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_EB_BUCKET=your-eb-bucket-name
DJANGO_SECRET_KEY=your-strong-random-secret-key
```

### 3. Elastic Beanstalk Environment Variables

Set these in EB Console (Configuration → Software → Environment properties):

```
DJANGO_SECRET_KEY=your-strong-random-secret-key
DEBUG=False
ALLOWED_HOSTS=your-app.elasticbeanstalk.com,your-custom-domain.com
DATABASE_URL=postgres://user:password@rds-endpoint:5432/dbname
SECURE_SSL_REDIRECT=True
CSRF_TRUSTED_ORIGINS=https://your-app.elasticbeanstalk.com
NYC_OPEN_DATA_APP_TOKEN=your-token (optional, for higher API rate limits)
```

## Deployment Configuration

### .ebextensions Files

The project includes three configuration files in `.ebextensions/`:

1. **01_packages.config** - Installs system dependencies
2. **02_django.config** - Runs migrations, collectstatic, and initial data ingestion
3. **03_cron.config** - Sets up daily data refresh at 2 AM UTC

### Data Fetching Strategy

#### Initial Deployment
On first deployment, the system automatically:
- Runs database migrations
- Collects static files
- Ingests initial data (limited to 1000 records for speed)
- Computes risk scores

#### Ongoing Updates
Daily cron jobs (2 AM UTC):
- Fetch latest HPD violations (5000 records)
- Fetch latest 311 complaints (5000 records)
- Recompute risk scores for all NTAs

## Deployment Process

### Option 1: Automatic Deployment via Travis CI

1. **Update .travis.yml** with your EB app and environment names:
   ```yaml
   deploy:
     app: TenantGuard       # Your EB application name
     env: tenantguard-env   # Your EB environment name
   ```

2. **Push to main or develop branch**:
   ```bash
   git add .
   git commit -m "Deploy to AWS EBS"
   git push origin main
   ```

3. **Monitor deployment** in Travis CI dashboard

### Option 2: Manual Deployment via EB CLI

1. **Initialize EB** (first time only):
   ```bash
   eb init -p python-3.13 TenantGuard --region us-east-1
   ```

2. **Create environment** (first time only):
   ```bash
   eb create tenantguard-env --database.engine postgres --database.size 10
   ```

3. **Deploy updates**:
   ```bash
   eb deploy
   ```

4. **Check status**:
   ```bash
   eb status
   eb health
   eb logs
   ```

## Data Management

### Manual Data Refresh

SSH into your EB instance and run:

```bash
# SSH to instance
eb ssh

# Activate virtual environment
source /var/app/venv/*/bin/activate
cd /var/app/current

# Run data ingestion
python manage.py ingest_all --limit 10000

# Compute risk scores
python manage.py compute_risk_scores
```

### Check Data Status

```bash
python manage.py shell

# In Django shell:
from mapview.models import HPDViolation, Complaint311, NTARiskScore

print(f"HPD Violations: {HPDViolation.objects.count()}")
print(f"311 Complaints: {Complaint311.objects.count()}")
print(f"Risk Scores: {NTARiskScore.objects.count()}")
```

## Monitoring

### Application Logs

```bash
# View recent logs
eb logs

# Tail logs in real-time
eb logs --stream
```

### Cron Job Logs

Check `/var/log/tenantguard_cron.log` for data refresh status:

```bash
eb ssh
sudo tail -f /var/log/tenantguard_cron.log
```

### Health Monitoring

- **EB Console**: Monitor instance health, requests, and errors
- **CloudWatch**: Set up alarms for CPU, memory, and error rates
- **Application Logs**: Check for Django errors and data ingestion issues

## Troubleshooting

### Data Not Loading

1. Check environment variables are set correctly
2. Verify DATABASE_URL includes PostGIS-enabled database
3. Check cron logs: `sudo cat /var/log/tenantguard_cron.log`
4. Manually run ingestion to see errors

### Database Connection Issues

1. Ensure RDS security group allows EB instance access
2. Verify DATABASE_URL format: `postgres://user:pass@host:5432/db`
3. Check PostGIS extension is installed

### Static Files Not Serving

1. Run `eb ssh` and check `/var/app/current/staticfiles/`
2. Verify `STATIC_ROOT` in settings.py
3. Re-run: `python manage.py collectstatic --noinput`

### Performance Issues

1. Increase instance size in EB configuration
2. Add database indexes for frequently queried fields
3. Implement caching with Redis/ElastiCache
4. Limit data ingestion batch sizes

## Scaling

### Auto Scaling

Configure in EB Console → Configuration → Capacity:
- Min instances: 1
- Max instances: 4
- Scaling triggers: CPU > 70% for 5 minutes

### Database Scaling

- Increase RDS instance size for better performance
- Add read replicas for heavy read workloads
- Enable Multi-AZ for high availability

## Security Best Practices

1. **Never commit secrets** to version control
2. **Use IAM roles** instead of access keys when possible
3. **Enable SSL/TLS** for all connections
4. **Rotate credentials** regularly
5. **Enable AWS WAF** for DDoS protection
6. **Regular security updates**: `eb upgrade`

## Cost Optimization

1. Use **t3.micro** or **t3.small** instances for development
2. Schedule **environment shutdown** during off-hours
3. Use **RDS reserved instances** for production
4. Enable **S3 lifecycle policies** for old logs
5. Monitor costs with **AWS Cost Explorer**

## CI/CD Pipeline

The Travis CI pipeline automatically:
1. ✅ Runs code formatting checks (Black)
2. ✅ Runs linting (Flake8)
3. ✅ Runs all tests with coverage
4. ✅ Reports coverage to Coveralls
5. ✅ Deploys to AWS EBS on main/develop branches

## Support

For issues or questions:
- Check application logs: `eb logs`
- Review Django logs in CloudWatch
- Consult AWS EBS documentation
- Contact development team

---

**Last Updated**: 2024
**Maintained By**: TenantGuard Development Team

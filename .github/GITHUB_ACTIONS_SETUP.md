# GitHub Actions Setup Guide

## Migration from Travis CI to GitHub Actions

This guide helps you set up GitHub Actions for CI/CD deployment to AWS Elastic Beanstalk.

## Prerequisites

You need the following information from your AWS/Travis setup:
- AWS Access Key ID
- AWS Secret Access Key
- Elastic Beanstalk Application Name
- Elastic Beanstalk Environment Name
- S3 Bucket Name (for EB deployments)

## Step-by-Step Setup

### 1. Add GitHub Secrets

Go to your repository on GitHub:
1. Click **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret**
3. Add the following secrets:

| Secret Name | Description | Example Value |
|------------|-------------|---------------|
| `AWS_ACCESS_KEY_ID` | Your AWS access key | `AKIAIOSFODNN7EXAMPLE` |
| `AWS_SECRET_ACCESS_KEY` | Your AWS secret key | `wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY` |
| `AWS_EB_APP` | Elastic Beanstalk app name | `tenantguard` |
| `AWS_EB_ENV` | Elastic Beanstalk environment | `tenantguard-prod` |
| `AWS_EB_BUCKET` | S3 bucket for deployments | `elasticbeanstalk-us-east-1-556154630982` |
| `COVERALLS_REPO_TOKEN` | (Optional) Coveralls token | Get from coveralls.io |

### 2. Find Your AWS Values

If you don't know these values, check:

**EB Application Name:**
```bash
aws elasticbeanstalk describe-applications --query 'Applications[*].ApplicationName'
```

**EB Environment Name:**
```bash
aws elasticbeanstalk describe-environments --query 'Environments[*].EnvironmentName'
```

**S3 Bucket:**
```bash
aws elasticbeanstalk describe-application-versions \
  --application-name YOUR_APP_NAME \
  --query 'ApplicationVersions[0].SourceBundle.S3Bucket'
```

Or check your Travis CI environment variables in the Travis dashboard.

### 3. Enable GitHub Actions

The workflow file `.github/workflows/deploy.yml` is already created. It will automatically run when you push to:
- `main`
- `develop`
- `deploy`

### 4. Test the Deployment

1. Commit and push this setup:
   ```bash
   git add .github/
   git commit -m "Add GitHub Actions CI/CD workflow"
   git push origin deploy
   ```

2. Go to your GitHub repo → **Actions** tab
3. You should see the workflow running

### 5. Disable Travis CI (Optional)

Once GitHub Actions is working:
1. Go to travis-ci.com
2. Find your repository
3. Click **More options** → **Settings**
4. Toggle off "Build pushed branches"

Or simply remove `.travis.yml` from your repo.

## What the Workflow Does

1. **Checkout code** - Gets your latest code
2. **Set up Python 3.13** - Matches your Travis setup
3. **Install dependencies** - Installs from requirements.txt
4. **Run Black** - Code formatting check
5. **Run Flake8** - Linting
6. **Run tests** - With coverage reporting
7. **Upload to Coveralls** - (if token is set)
8. **Deploy to EB** - Only if tests pass

## Differences from Travis CI

| Feature | Travis CI | GitHub Actions |
|---------|-----------|----------------|
| Build time | ~5-10 min | ~3-8 min (usually faster) |
| Free tier | Limited | 2000 min/month (free for public repos) |
| Logs | Travis dashboard | GitHub Actions tab |
| Secrets | Travis settings | GitHub repo settings |

## Troubleshooting

### Deployment fails with "Access Denied"
- Check that `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` are correct
- Verify your AWS user has `AWSElasticBeanstalkFullAccess` permission

### "Application not found"
- Check `AWS_EB_APP` matches your actual EB application name
- Run `aws elasticbeanstalk describe-applications` to verify

### "Environment not found"
- Check `AWS_EB_ENV` matches your actual EB environment name
- Run `aws elasticbeanstalk describe-environments` to verify

### Tests pass but deployment skipped
- Make sure you're pushing to `main`, `develop`, or `deploy` branch
- Check the Actions tab for error messages

## Monitoring

- **GitHub Actions**: Repo → Actions tab
- **AWS EB**: AWS Console → Elastic Beanstalk → Your environment
- **Logs**: GitHub Actions provides real-time logs for each step

## Support

If you encounter issues:
1. Check the Actions tab for detailed error logs
2. Verify all secrets are set correctly
3. Ensure your AWS credentials have the necessary permissions

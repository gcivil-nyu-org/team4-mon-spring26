# TenantGuard NYC

[![Build Status](https://app.travis-ci.com/gcivil-nyu-org/team4-mon-spring26.svg?branch=develop)](https://app.travis-ci.com/gcivil-nyu-org/team4-mon-spring26)
[![Coverage Status](https://coveralls.io/repos/github/gcivil-nyu-org/team4-mon-spring26/badge.svg?branch=develop)](https://coveralls.io/github/gcivil-nyu-org/team4-mon-spring26?branch=develop)

ML-powered web app to predict NYC building housing violations and facilitate tenant organizing.

## Quick Links

- **[View Scrum Schedule](https://docs.google.com/spreadsheets/u/1/d/1Ep7P7--u7woJ2tpBLLidbiIUVIILQp0vciva1QV5LpA/preview)** &nbsp;&nbsp;&nbsp;&nbsp; | &nbsp;&nbsp;&nbsp;&nbsp; **[Edit Scrum Schedule](https://docs.google.com/spreadsheets/d/1Ep7P7--u7woJ2tpBLLidbiIUVIILQp0vciva1QV5LpA/edit?gid=904893745#gid=904893745)**

- **[View Scrum Board](https://docs.google.com/spreadsheets/d/1OOE0XUMu22ikPVS02noCb3MIWEPZ7TqPRhlNJndYJx8/edit?usp=sharing)**

- **Live Proposal Document**: [Link](https://docs.google.com/document/d/1TRgnKfPCHs1N4AuZm2y5Q7pzO4U34T0YO25_MCShGVY/edit?usp=sharing)
- **Final Proposal**: [docs/proposal.pdf](docs/proposal.pdf)
- **TenantGuard Pitch**: [Link](https://docs.google.com/presentation/d/1X15IEGGepDtGm3xI6VvZ3TU_idvH2a6g/edit?usp=sharing&ouid=113186868007033640980&rtpof=true&sd=true)
- **Live Demo (AWS EB)**: [https://tenantguard-env.eba-vwctwzqr.us-east-1.elasticbeanstalk.com](https://tenantguard-env.eba-vwctwzqr.us-east-1.elasticbeanstalk.com)

## Tech Stack

- Django 5.0+
- scikit-learn (ML)
- PostgreSQL
- NYC Open Data SODA API

## Setup

```bash
# Clone and setup
git clone https://github.com/gcivil-nyu-org/team4-mon-spring26.git
cd team4-mon-spring26
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your settings

# Database
python manage.py migrate

# Run
python manage.py runserver
```

## Deploy to AWS Elastic Beanstalk (Production)

### 1) Prerequisites

- AWS account with permissions for Elastic Beanstalk, EC2, S3, CloudWatch, and RDS
- AWS CLI + EB CLI installed and configured
- Python virtual environment active

### 2) Create PostgreSQL (RDS)

Create an RDS PostgreSQL instance in the same VPC/security context as your Elastic Beanstalk environment.

Collect its connection details and build:

`DATABASE_URL=postgres://USERNAME:PASSWORD@HOST:5432/DBNAME`

### 3) Initialize and create Elastic Beanstalk environment

Use the same **application name** and **environment name** as in [`.travis.yml`](.travis.yml) (`TenantGuard` / `tenantguard-env`) so Travis deploys to the right place.

```bash
eb init TenantGuard --region us-east-1 --platform "64bit Amazon Linux 2023 v4.11.0 running Python 3.13"
eb create tenantguard-env --database.engine postgres --database.size 10 --single --instance-types t3.small
```

Adjust instance size and DB for cost. For Travis deploy, set `AWS_EB_BUCKET` to your account’s default bucket (often `elasticbeanstalk-<region>-<account-id>`).

### 4) Set production environment variables

```bash
eb setenv \
DJANGO_SECRET_KEY="<strong-secret>" \
DEBUG=False \
ALLOWED_HOSTS="<your-eb-domain>,<your-custom-domain>" \
CSRF_TRUSTED_ORIGINS="https://<your-eb-domain>,https://<your-custom-domain>" \
DATABASE_URL="postgres://USERNAME:PASSWORD@HOST:5432/DBNAME" \
DB_SSL_REQUIRE=True
```

### 5) Deploy

```bash
eb deploy
eb open
```

### Travis CI (auto-deploy `develop`)

1. Create an S3 bucket for EB application versions (any unique name in `us-east-1`).
2. In [Travis repo settings → Environment variables](https://app.travis-ci.com/), add (not displayed in build logs):
   - `AWS_ACCESS_KEY_ID`
   - `AWS_SECRET_ACCESS_KEY`
   - `AWS_EB_BUCKET` (that bucket name)
3. IAM user needs permission to upload to the bucket and to create EB application versions / update the environment (e.g. `AdministratorAccess-AWSElasticBeanstalk` plus S3 rights to the bucket, or a tailored policy).
4. Push to `develop` or `main`: tests run first; deploy runs **only** if the script stage passes.

### GitHub: require green Travis before merge

Direct pushes to `develop` may be blocked (org rules). Merge a PR (for example from `chore/aws-eb-simplify` or your feature branch) after Travis is green.

Repo **Settings → Branches → Branch protection rule** for `develop`:

- Enable **Require status checks to pass before merging** and **Require branches to be up to date before merging**.
- Select the Travis check that appears on pull requests (open a test PR once to discover the exact name).
- Optionally **Require a pull request before merging**.

### Notes

- `Procfile` runs Gunicorn; WhiteNoise serves `/static` from collected files.
- [`.ebextensions/02_django.config`](.ebextensions/02_django.config) runs `migrate` and `collectstatic` on deploy.
- Initial map data: run `python manage.py ingest_all --limit 2000` (e.g. EB SSH or one-off job) if you need a populated demo.
- For production media uploads, prefer S3 (instance-local media is ephemeral).

## Streamlit Demo (Live Link Ready)

You can deploy a shareable live demo with Streamlit Community Cloud using the existing processed GeoJSON files.

### Run locally

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

### Deploy to Streamlit Cloud

1. Push your branch to GitHub.
2. Go to [share.streamlit.io](https://share.streamlit.io/) and sign in with GitHub.
3. Create a new app:
   - Repository: `gcivil-nyu-org/team4-mon-spring26`
   - Branch: your feature branch
   - Main file path: `streamlit_app.py`
4. Click **Deploy**.
5. Copy the generated app URL and replace the `Live Demo` placeholder in this README.

## Team

- **Product Owner**: Jithendra ([@jithendra1798](https://github.com/jithendra1798))
- **Dev Team**: Annie Jain, Raffael Davila, Sakshi Sawant, Yatharth Mogra, Jithendra Puppala

NYU Tandon - CS-GY 6063 - Spring 2025

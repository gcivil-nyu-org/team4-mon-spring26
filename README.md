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
- **Live Demo**: [Add link when deployed]

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

```bash
eb init
eb create tenantguard-prod
```

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

### Notes

- `Procfile` runs Gunicorn for Django.
- `.ebextensions/01_django.config` runs `migrate` and `collectstatic` automatically on deploy.
- `.ebextensions/02_staticfiles.config` maps `/static` for serving collected static assets.
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

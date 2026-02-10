# TenantGuard NYC

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
git clone https://github.com/jithendra1798/TenatGaurdNYC.git
cd TenatGaurdNYC
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

## Project Structure

```
TenatGaurdNYC/
├── buildings/        # Building data & ML models
├── users/           # Authentication
├── forums/          # Tenant chat
├── static/          # Frontend assets
├── templates/       # HTML templates
├── docs/            # Documentation & proposal
└── tests/           # Test suite
```

## Team

- **Product Owner**: Jithendra ([@jithendra1798](https://github.com/jithendra1798))
- **Dev Team**: Annie Jain, Raffael Davila, Sakshi Sawant, Yatharth Mogra, Jithendra Puppala

NYU Tandon - CS-GY 6063 - Spring 2025

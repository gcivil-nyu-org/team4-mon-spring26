"""Run the full data-ingestion pipeline in one command.

Steps executed in order:
1. Ingest HPD violations
2. Ingest 311 housing complaints
3. Compute per-NTA risk scores
"""

from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Run the full ingestion pipeline: HPD violations → 311 complaints → risk scores"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=10000,
            help="Max records per data source (default: %(default)s)",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear existing data before ingesting",
        )

    def handle(self, *args, **options):
        limit = options["limit"]
        clear = options["clear"]

        self.stdout.write(
            self.style.MIGRATE_HEADING("Step 1/3: Ingesting HPD violations...")
        )
        call_command(
            "ingest_hpd_violations",
            limit=limit,
            clear=clear,
            stdout=self.stdout,
            stderr=self.stderr,
        )

        self.stdout.write(
            self.style.MIGRATE_HEADING("Step 2/3: Ingesting 311 complaints...")
        )
        call_command(
            "ingest_311_complaints",
            limit=limit,
            clear=clear,
            stdout=self.stdout,
            stderr=self.stderr,
        )

        self.stdout.write(
            self.style.MIGRATE_HEADING("Step 3/3: Computing risk scores...")
        )
        call_command("compute_risk_scores", stdout=self.stdout, stderr=self.stderr)

        self.stdout.write(self.style.SUCCESS("\n✅  Full ingestion pipeline complete."))

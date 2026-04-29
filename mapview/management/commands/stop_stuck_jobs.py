"""Management command to stop stuck ingestion jobs."""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from mapview.models import IngestionJob


class Command(BaseCommand):
    help = "Stop ingestion jobs that have been running for more than 24 hours"

    def add_arguments(self, parser):
        parser.add_argument(
            "--hours",
            type=int,
            default=24,
            help="Stop jobs running longer than this many hours (default: 24)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be stopped without actually stopping",
        )

    def handle(self, *args, **options):
        hours_threshold = options["hours"]
        dry_run = options["dry_run"]

        cutoff_time = timezone.now() - timedelta(hours=hours_threshold)

        stuck_jobs = IngestionJob.objects.filter(
            status=IngestionJob.STATUS_RUNNING, started_at__lt=cutoff_time
        )

        if not stuck_jobs.exists():
            self.stdout.write(
                self.style.SUCCESS(
                    f"No jobs running longer than {hours_threshold} hours"
                )
            )
            return

        for job in stuck_jobs:
            runtime = timezone.now() - job.started_at
            hours = runtime.total_seconds() / 3600

            if dry_run:
                self.stdout.write(
                    f"Would stop Job #{job.id} (running for {hours:.1f} hours)"
                )
            else:
                job.status = IngestionJob.STATUS_FAILED
                job.error_message = (
                    f"Automatically stopped - job was stuck for {hours:.1f} hours. "
                    f"This was likely due to inefficient spatial NTA assignment "
                    f"(fixed in recent deployment)."
                )
                job.completed_at = timezone.now()
                job.save()

                self.stdout.write(
                    self.style.WARNING(
                        f"Stopped Job #{job.id} (was running for {hours:.1f} hours)"
                    )
                )

        if not dry_run:
            self.stdout.write(
                self.style.SUCCESS(f"Stopped {stuck_jobs.count()} stuck job(s)")
            )

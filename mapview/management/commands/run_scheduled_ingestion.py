"""Check the IngestionSchedule and run ingestion if due.

Designed to be called by a cron job (e.g. every hour via EB cron).
If the schedule is enabled and next_run_at has passed, it creates
an IngestionJob and triggers the pipeline.

Usage:
    python manage.py run_scheduled_ingestion
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from mapview.ingestion import is_job_running, run_ingestion_job
from mapview.models import IngestionJob, IngestionSchedule


class Command(BaseCommand):
    help = "Run scheduled data ingestion if due"

    def handle(self, *args, **options):
        schedule = IngestionSchedule.load()

        if not schedule.is_enabled:
            self.stdout.write("Scheduled ingestion is disabled.")
            return

        now = timezone.now()

        if schedule.next_run_at and schedule.next_run_at > now:
            self.stdout.write(
                f"Not yet due. Next run at {schedule.next_run_at.isoformat()}"
            )
            return

        if is_job_running():
            self.stdout.write("A job is already running. Skipping.")
            return

        # Create and start the ingestion job
        job = IngestionJob.objects.create(
            trigger_type=IngestionJob.TRIGGER_SCHEDULED,
            requested_limit=schedule.record_limit,
            sources=schedule.sources,
        )
        run_ingestion_job(job.pk)

        # Update schedule timestamps
        schedule.last_run_at = now
        if schedule.interval_unit == IngestionSchedule.UNIT_HOURS:
            delta = timedelta(hours=schedule.interval_value)
        else:
            delta = timedelta(days=schedule.interval_value)
        schedule.next_run_at = now + delta
        schedule.save()

        self.stdout.write(
            self.style.SUCCESS(
                f"Scheduled ingestion job #{job.pk} started. "
                f"Next run at {schedule.next_run_at.isoformat()}"
            )
        )

"""Fetch housing-related 311 complaints from the NYC Open Data SODA API."""

import logging
from datetime import datetime

import requests
from django.conf import settings
from django.core.management.base import BaseCommand

from mapview.models import Complaint311

logger = logging.getLogger(__name__)

COMPLAINTS_311_URL = "https://data.cityofnewyork.us/resource/erm2-nwe9.json"
BATCH_SIZE = 5000
DEFAULT_LIMIT = 50000

HOUSING_COMPLAINT_TYPES = [
    "HEAT/HOT WATER",
    "PLUMBING",
    "PAINT/PLASTER",
    "WATER LEAK",
    "GENERAL CONSTRUCTION",
    "ELECTRIC",
    "DOOR/WINDOW",
    "FLOORING/STAIRS",
    "ELEVATOR",
    "SAFETY",
    "APPLIANCE",
    "Noise - Residential",
    "UNSANITARY CONDITION",
    "PEST CONTROL",
]


def _parse_datetime(value):
    """Return a datetime from an ISO-ish string, or None."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("T", " ").split(".")[0])
    except (ValueError, AttributeError):
        return None


class Command(BaseCommand):
    help = "Ingest housing-related 311 complaints from the NYC Open Data SODA API"

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=DEFAULT_LIMIT,
            help="Maximum records to fetch (default: %(default)s)",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete all existing complaints before ingesting",
        )

    def handle(self, *args, **options):
        limit = options["limit"]

        if options["clear"]:
            deleted, _ = Complaint311.objects.all().delete()
            self.stdout.write(f"Cleared {deleted} existing complaint records.")

        app_token = getattr(settings, "NYC_OPEN_DATA_APP_TOKEN", "")
        headers = {"X-App-Token": app_token} if app_token else {}

        type_clauses = " OR ".join(f"complaint_type='{ct}'" for ct in HOUSING_COMPLAINT_TYPES)
        where = f"({type_clauses}) AND latitude IS NOT NULL AND longitude IS NOT NULL"

        offset = 0
        total_created = 0
        total_updated = 0

        while offset < limit:
            batch_limit = min(BATCH_SIZE, limit - offset)
            params = {
                "$limit": batch_limit,
                "$offset": offset,
                "$order": "created_date DESC",
                "$where": where,
            }

            try:
                resp = requests.get(COMPLAINTS_311_URL, params=params, headers=headers, timeout=30)
                resp.raise_for_status()
                records = resp.json()
            except requests.RequestException as exc:
                self.stderr.write(self.style.ERROR(f"API request failed at offset {offset}: {exc}"))
                break

            if not records:
                break

            for rec in records:
                key = rec.get("unique_key")
                if not key:
                    continue

                _, created = Complaint311.objects.update_or_create(
                    unique_key=key,
                    defaults={
                        "created_date": _parse_datetime(rec.get("created_date")),
                        "closed_date": _parse_datetime(rec.get("closed_date")),
                        "agency": rec.get("agency", "") or "",
                        "complaint_type": rec.get("complaint_type", "") or "",
                        "descriptor": rec.get("descriptor", "") or "",
                        "location_type": rec.get("location_type", "") or "",
                        "incident_address": rec.get("incident_address", "") or "",
                        "incident_zip": rec.get("incident_zip", "") or "",
                        "borough": rec.get("borough", "") or "",
                        "status": rec.get("status", "") or "",
                        "resolution_description": rec.get("resolution_description", "") or "",
                        "bbl": rec.get("bbl", "") or "",
                        "latitude": float(rec["latitude"]) if rec.get("latitude") else None,
                        "longitude": float(rec["longitude"]) if rec.get("longitude") else None,
                    },
                )
                if created:
                    total_created += 1
                else:
                    total_updated += 1

            self.stdout.write(f"  batch offset={offset}  fetched={len(records)}")
            offset += len(records)
            if len(records) < batch_limit:
                break

        self.stdout.write(
            self.style.SUCCESS(f"311 ingest complete — created={total_created}  updated={total_updated}")
        )

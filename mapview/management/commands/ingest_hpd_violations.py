"""Fetch HPD housing-violation records from the NYC Open Data SODA API."""

import logging
from datetime import datetime

import requests
from django.conf import settings
from django.core.management.base import BaseCommand

from mapview.models import HPDViolation

logger = logging.getLogger(__name__)

HPD_VIOLATIONS_URL = "https://data.cityofnewyork.us/resource/wvxf-dwi5.json"
BATCH_SIZE = 5000
DEFAULT_LIMIT = 50000


def _parse_date(value):
    """Return a date from an ISO-ish string, or None."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.split("T")[0]).date()
    except (ValueError, AttributeError):
        return None


def _extract_violation_class(record):
    """Return a normalized HPD violation class from the API payload."""
    raw_value = record.get("violationclass") or record.get("class") or ""
    return str(raw_value).strip().upper()


class Command(BaseCommand):
    help = "Ingest HPD violations from the NYC Open Data SODA API"

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=DEFAULT_LIMIT,
            help="Maximum number of records to fetch (default: %(default)s)",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete all existing violations before ingesting",
        )

    def handle(self, *args, **options):
        limit = options["limit"]

        if options["clear"]:
            deleted, _ = HPDViolation.objects.all().delete()
            self.stdout.write(f"Cleared {deleted} existing violation records.")

        app_token = getattr(settings, "NYC_OPEN_DATA_APP_TOKEN", "")
        headers = {"X-App-Token": app_token} if app_token else {}

        offset = 0
        total_created = 0
        total_updated = 0

        while offset < limit:
            batch_limit = min(BATCH_SIZE, limit - offset)
            params = {
                "$limit": batch_limit,
                "$offset": offset,
                "$order": "inspectiondate DESC",
                "$where": "latitude IS NOT NULL AND longitude IS NOT NULL",
            }

            try:
                resp = requests.get(
                    HPD_VIOLATIONS_URL, params=params, headers=headers, timeout=30
                )
                resp.raise_for_status()
                records = resp.json()
            except requests.RequestException as exc:
                self.stderr.write(
                    self.style.ERROR(f"API request failed at offset {offset}: {exc}")
                )
                break

            if not records:
                break

            for rec in records:
                vid = rec.get("violationid")
                if not vid:
                    continue

                _, created = HPDViolation.objects.update_or_create(
                    violation_id=int(vid),
                    defaults={
                        "bbl": rec.get("bbl", "") or "",
                        "borough": rec.get("boroname", "") or "",
                        "house_number": rec.get("housenumber", "") or "",
                        "street_name": rec.get("streetname", "") or "",
                        "apartment": rec.get("apartment", "") or "",
                        "zip_code": rec.get("zip", "") or "",
                        "violation_class": _extract_violation_class(rec),
                        "inspection_date": _parse_date(rec.get("inspectiondate")),
                        "approved_date": _parse_date(rec.get("approveddate")),
                        "nov_description": rec.get("novdescription", "") or "",
                        "nov_issued_date": _parse_date(rec.get("novissueddate")),
                        "current_status": rec.get("currentstatus", "") or "",
                        "current_status_id": (
                            int(rec["currentstatusid"])
                            if rec.get("currentstatusid")
                            else None
                        ),
                        "violation_status": rec.get("violationstatus", "") or "",
                        "violation_status_date": _parse_date(
                            rec.get("violationstatusdate")
                        ),
                        "latitude": (
                            float(rec["latitude"]) if rec.get("latitude") else None
                        ),
                        "longitude": (
                            float(rec["longitude"]) if rec.get("longitude") else None
                        ),
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
            self.style.SUCCESS(
                f"HPD ingest complete — created={total_created}  updated={total_updated}"
            )
        )

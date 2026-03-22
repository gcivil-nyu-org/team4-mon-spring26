"""Compute per-NTA risk scores from ingested violation and complaint data.

For each NTA neighbourhood the command:
1. Spatially assigns un-coded violations / complaints to their NTA using
   point-in-polygon against the processed NTA GeoJSON.
2. Aggregates violation + complaint counts.
3. Calculates a 0-10 risk score (10 = safest).
4. Persists the result in the NTARiskScore table.
"""

import json
import math
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Count

from mapview.models import Complaint311, HPDViolation, NTARiskScore

NTA_GEOJSON_PATH = (
    Path(settings.BASE_DIR) / "data" / "processed" / "nyc_nta_phase1.geojson"
)


class Command(BaseCommand):
    help = "Compute NTA-level risk scores from ingested violations and complaints"

    def handle(self, *args, **options):
        # ---- load NTA definitions ------------------------------------------
        try:
            with NTA_GEOJSON_PATH.open("r", encoding="utf-8") as fh:
                nta_data = json.load(fh)
        except FileNotFoundError:
            self.stderr.write(
                self.style.ERROR(
                    "NTA GeoJSON not found. Run prepare_nta_geojson first."
                )
            )
            return

        nta_lookup = {}
        for feature in nta_data.get("features", []):
            props = feature.get("properties", {})
            code = props.get("nta_code")
            if code:
                nta_lookup[code] = {
                    "nta_name": props.get("nta_name", ""),
                    "borough": props.get("borough", ""),
                }

        self.stdout.write(f"Loaded {len(nta_lookup)} NTA neighbourhoods.")

        # ---- spatial assignment of untagged records ------------------------
        self._assign_nta_codes(nta_data)

        # ---- aggregate & score per NTA -------------------------------------
        scored = 0
        for nta_code, info in nta_lookup.items():
            violations_qs = HPDViolation.objects.filter(nta_code=nta_code)
            complaints_qs = Complaint311.objects.filter(nta_code=nta_code)

            total_violations = violations_qs.count()
            total_complaints = complaints_qs.count()
            class_a = violations_qs.filter(violation_class="A").count()
            class_b = violations_qs.filter(violation_class="B").count()
            class_c = violations_qs.filter(violation_class="C").count()

            # Top complaint types
            top_types = (
                complaints_qs.values("complaint_type")
                .annotate(n=Count("id"))
                .order_by("-n")[:5]
            )
            top_complaint_types = [t["complaint_type"] for t in top_types]

            # Weighted issue count → risk score
            weighted = (class_c * 3) + (class_b * 2) + class_a + total_complaints
            if weighted == 0:
                risk_score = 10.0
            else:
                risk_score = round(
                    max(0.0, min(10.0, 10.0 - math.log1p(weighted) * 1.2)), 1
                )

            # Human-readable summary
            if risk_score <= 3.0:
                summary = (
                    f"High-risk area — {total_violations} HPD violations and "
                    f"{total_complaints} complaints on record. Immediate concerns present."
                )
            elif risk_score <= 6.0:
                summary = (
                    f"Moderate-risk area — {total_violations} violations and "
                    f"{total_complaints} complaints. Some issues but generally manageable."
                )
            else:
                summary = (
                    f"Lower-risk area — {total_violations} violations and "
                    f"{total_complaints} complaints. Relatively stable conditions."
                )

            NTARiskScore.objects.update_or_create(
                nta_code=nta_code,
                defaults={
                    "nta_name": info["nta_name"],
                    "borough": info["borough"],
                    "total_violations": total_violations,
                    "total_complaints": total_complaints,
                    "class_a_violations": class_a,
                    "class_b_violations": class_b,
                    "class_c_violations": class_c,
                    "risk_score": risk_score,
                    "top_complaint_types": top_complaint_types,
                    "summary": summary,
                },
            )
            scored += 1

        self.stdout.write(
            self.style.SUCCESS(f"Computed risk scores for {scored} NTA neighbourhoods.")
        )

    # ---------------------------------------------------------------------- #
    def _assign_nta_codes(self, nta_data):
        """Point-in-polygon assignment using shapely spatial index."""
        try:
            from shapely.geometry import Point, shape
            from shapely.strtree import STRtree
        except ImportError:
            self.stderr.write(
                self.style.WARNING(
                    "shapely not installed — skipping spatial NTA assignment."
                )
            )
            return

        nta_geoms = []
        nta_codes = []
        for feature in nta_data.get("features", []):
            code = feature.get("properties", {}).get("nta_code")
            if code:
                nta_geoms.append(shape(feature["geometry"]))
                nta_codes.append(code)

        tree = STRtree(nta_geoms)

        # -- violations
        unassigned_v = HPDViolation.objects.filter(
            nta_code="", latitude__isnull=False, longitude__isnull=False
        )
        v_assigned = 0
        for v in unassigned_v.iterator(chunk_size=2000):
            pt = Point(v.longitude, v.latitude)
            for idx in tree.query(pt):
                if nta_geoms[int(idx)].contains(pt):
                    v.nta_code = nta_codes[int(idx)]
                    v.save(update_fields=["nta_code"])
                    v_assigned += 1
                    break
        self.stdout.write(f"  NTA-tagged {v_assigned} violations.")

        # -- complaints
        unassigned_c = Complaint311.objects.filter(
            nta_code="", latitude__isnull=False, longitude__isnull=False
        )
        c_assigned = 0
        for c in unassigned_c.iterator(chunk_size=2000):
            pt = Point(c.longitude, c.latitude)
            for idx in tree.query(pt):
                if nta_geoms[int(idx)].contains(pt):
                    c.nta_code = nta_codes[int(idx)]
                    c.save(update_fields=["nta_code"])
                    c_assigned += 1
                    break
        self.stdout.write(f"  NTA-tagged {c_assigned} complaints.")

import json
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import (
    AreaSubscription,
    Complaint311,
    HPDViolation,
    IngestionJob,
    IngestionSchedule,
    Notification,
    NTARiskScore,
    RiskScoreHistory,
    ScoreRecencyConfig,
    ScoreThreshold,
)

User = get_user_model()

# ============================================================ #
#  Sprint 1 tests (unchanged)
# ============================================================ #


class DashboardRouteTests(TestCase):
    def test_dashboard_route_returns_200(self):
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)


class GeoJsonEndpointTests(TestCase):
    def test_geojson_endpoint_has_required_schema(self):
        response = self.client.get(reverse("nta-geojson"))
        self.assertEqual(response.status_code, 200)

        payload = response.json()
        self.assertEqual(payload["type"], "FeatureCollection")
        self.assertGreater(len(payload["features"]), 0)

        first = payload["features"][0]
        props = first["properties"]
        for key in (
            "nta_code",
            "nta_name",
            "borough",
            "placeholder_score",
            "placeholder_summary",
            "top_issues",
        ):
            self.assertIn(key, props)

    def test_boundaries_endpoint_supports_levels(self):
        for level in ("nta", "mid", "block"):
            response = self.client.get(reverse("boundaries"), {"level": level})
            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(payload["type"], "FeatureCollection")
            self.assertGreater(len(payload["features"]), 0)

    def test_boundaries_endpoint_rejects_invalid_level(self):
        response = self.client.get(reverse("boundaries"), {"level": "invalid"})
        self.assertEqual(response.status_code, 400)


class GeocodeEndpointTests(TestCase):
    def test_rejects_short_query(self):
        response = self.client.get(reverse("geocode"), {"q": "ab"})
        self.assertEqual(response.status_code, 400)

    @override_settings(MAPBOX_ACCESS_TOKEN="test-token")
    @patch("mapview.views.requests.get")
    def test_geocode_success_contract(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "features": [
                {
                    "place_name": "123 Prince St, New York, New York 10012, United States",
                    "center": [-73.997, 40.724],
                }
            ]
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        response = self.client.get(reverse("geocode"), {"q": "123 Prince St"})
        self.assertEqual(response.status_code, 200)

        payload = response.json()
        self.assertEqual(payload["query"], "123 Prince St")
        self.assertIn("label", payload)
        self.assertEqual(payload["lng"], -73.997)
        self.assertEqual(payload["lat"], 40.724)


# ============================================================ #
#  Sprint 2 – Data models
# ============================================================ #


class HPDViolationModelTests(TestCase):
    def test_create_violation(self):
        v = HPDViolation.objects.create(
            violation_id=12345,
            bbl="1234567890",
            borough="MANHATTAN",
            house_number="123",
            street_name="Main St",
            violation_class="C",
            inspection_date=date(2025, 6, 1),
            nta_code="MN01",
            latitude=40.72,
            longitude=-73.99,
        )
        self.assertEqual(v.address, "123 Main St")
        self.assertEqual(str(v), "HPD-12345 (Class C) 123 Main St")

    def test_violation_ordering(self):
        HPDViolation.objects.create(
            violation_id=1, violation_class="A", inspection_date=date(2025, 1, 1)
        )
        HPDViolation.objects.create(
            violation_id=2, violation_class="B", inspection_date=date(2025, 6, 1)
        )
        first = HPDViolation.objects.first()
        self.assertEqual(first.violation_id, 2)


class Complaint311ModelTests(TestCase):
    def test_create_complaint(self):
        c = Complaint311.objects.create(
            unique_key="99999",
            complaint_type="HEAT/HOT WATER",
            borough="BROOKLYN",
            nta_code="BK01",
            latitude=40.68,
            longitude=-73.95,
        )
        self.assertEqual(str(c), "311-99999: HEAT/HOT WATER")


class NTARiskScoreModelTests(TestCase):
    def test_create_score(self):
        s = NTARiskScore.objects.create(
            nta_code="MN01",
            nta_name="Test Neighborhood",
            borough="MANHATTAN",
            risk_score=6.5,
            total_violations=120,
            total_complaints=80,
            top_complaint_types=["HEAT/HOT WATER", "PLUMBING"],
        )
        self.assertIn("6.5", str(s))
        self.assertEqual(s.top_complaint_types, ["HEAT/HOT WATER", "PLUMBING"])


# ============================================================ #
#  Sprint 2 – NTA Violations API
# ============================================================ #


class NTAViolationsEndpointTests(TestCase):
    def test_requires_nta_code(self):
        response = self.client.get(reverse("nta-violations"))
        self.assertEqual(response.status_code, 400)

    def test_returns_empty_for_unknown_nta(self):
        response = self.client.get(reverse("nta-violations"), {"nta_code": "ZZ99"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 0)

    def test_returns_violations_for_nta(self):
        HPDViolation.objects.create(
            violation_id=100,
            violation_class="B",
            borough="MANHATTAN",
            house_number="10",
            street_name="Broadway",
            nta_code="MN01",
            inspection_date=date(2025, 3, 15),
            latitude=40.72,
            longitude=-74.0,
        )
        HPDViolation.objects.create(
            violation_id=101,
            violation_class="C",
            borough="MANHATTAN",
            house_number="20",
            street_name="Broadway",
            nta_code="MN01",
            latitude=40.72,
            longitude=-74.0,
        )
        response = self.client.get(reverse("nta-violations"), {"nta_code": "MN01"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 2)
        self.assertEqual(data["nta_code"], "MN01")

    def test_respects_limit_parameter(self):
        for i in range(5):
            HPDViolation.objects.create(
                violation_id=200 + i, violation_class="A", nta_code="MN02"
            )
        response = self.client.get(
            reverse("nta-violations"), {"nta_code": "MN02", "limit": 2}
        )
        self.assertEqual(response.json()["count"], 2)


# ============================================================ #
#  Sprint 2 – NTA Complaints API
# ============================================================ #


class NTAComplaintsEndpointTests(TestCase):
    def test_requires_nta_code(self):
        response = self.client.get(reverse("nta-complaints"))
        self.assertEqual(response.status_code, 400)

    def test_returns_empty_for_unknown_nta(self):
        response = self.client.get(reverse("nta-complaints"), {"nta_code": "ZZ99"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 0)

    def test_returns_complaints_for_nta(self):
        Complaint311.objects.create(
            unique_key="C001",
            complaint_type="HEAT/HOT WATER",
            borough="BRONX",
            nta_code="BX01",
            incident_address="55 Grand Concourse",
            status="Open",
            latitude=40.82,
            longitude=-73.92,
            created_date=timezone.now(),
        )
        response = self.client.get(reverse("nta-complaints"), {"nta_code": "BX01"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["complaints"][0]["complaint_type"], "HEAT/HOT WATER")


# ============================================================ #
#  Sprint 2 – NTA Risk Summary API
# ============================================================ #


class NTARiskSummaryEndpointTests(TestCase):
    def test_requires_nta_code(self):
        response = self.client.get(reverse("nta-risk-summary"))
        self.assertEqual(response.status_code, 400)

    def test_returns_404_for_unknown_nta(self):
        response = self.client.get(reverse("nta-risk-summary"), {"nta_code": "ZZ99"})
        self.assertEqual(response.status_code, 404)

    def test_returns_risk_summary(self):
        NTARiskScore.objects.create(
            nta_code="MN05",
            nta_name="East Village",
            borough="MANHATTAN",
            risk_score=4.2,
            total_violations=200,
            total_complaints=150,
            class_a_violations=50,
            class_b_violations=80,
            class_c_violations=70,
            top_complaint_types=["HEAT/HOT WATER", "PLUMBING", "PAINT/PLASTER"],
            summary="Moderate-risk area.",
        )
        response = self.client.get(reverse("nta-risk-summary"), {"nta_code": "MN05"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["risk_score"], 4.2)
        self.assertEqual(data["nta_name"], "East Village")
        self.assertEqual(len(data["top_complaint_types"]), 3)
        self.assertIn("last_updated", data)


# ============================================================ #
#  Sprint 2 – Boundary overlay uses DB scores
# ============================================================ #


class BoundaryDBScoreOverlayTests(TestCase):
    """When NTARiskScore rows exist, the boundary API should overlay them."""

    def test_boundary_uses_db_score_when_available(self):
        # Grab any NTA code from the actual GeoJSON
        response = self.client.get(reverse("boundaries"), {"level": "nta"})
        payload = response.json()
        sample_code = payload["features"][0]["properties"]["nta_code"]
        payload["features"][0]["properties"]["placeholder_score"]

        # Insert a DB score for that NTA
        NTARiskScore.objects.create(
            nta_code=sample_code,
            nta_name="Test",
            borough="TEST",
            risk_score=2.5,
            total_violations=999,
            total_complaints=888,
            summary="DB-sourced summary.",
        )

        response2 = self.client.get(reverse("boundaries"), {"level": "nta"})
        payload2 = response2.json()
        matched = [
            f
            for f in payload2["features"]
            if f["properties"]["nta_code"] == sample_code
        ]
        self.assertTrue(matched)
        self.assertEqual(matched[0]["properties"]["placeholder_score"], 2.5)
        self.assertEqual(matched[0]["properties"]["total_violations"], 999)


# ============================================================ #
#  ScoreThreshold model
# ============================================================ #


class ScoreThresholdModelTests(TestCase):
    def test_str(self):
        t = ScoreThreshold.objects.create(
            name="High Risk", color="#dc2626", max_score=5.0
        )
        self.assertIn("High Risk", str(t))
        self.assertIn("5.0", str(t))


# ============================================================ #
#  Dashboard renders thresholds from DB
# ============================================================ #


class DashboardThresholdTests(TestCase):
    def test_dashboard_uses_db_thresholds(self):
        ScoreThreshold.objects.create(name="Bad", color="#ff0000", max_score=3.0)
        ScoreThreshold.objects.create(name="OK", color="#00ff00", max_score=10.0)
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "#ff0000")


# ============================================================ #
#  Geocode edge cases
# ============================================================ #


class GeocodeEdgeCaseTests(TestCase):
    @override_settings(MAPBOX_ACCESS_TOKEN="")
    def test_geocode_no_token(self):
        response = self.client.get(reverse("geocode"), {"q": "123 Main St"})
        self.assertEqual(response.status_code, 503)

    @override_settings(MAPBOX_ACCESS_TOKEN="test-token")
    @patch("mapview.views.requests.get")
    def test_geocode_no_features(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {"features": []}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        response = self.client.get(reverse("geocode"), {"q": "Nonexistent Place"})
        self.assertEqual(response.status_code, 404)

    @override_settings(MAPBOX_ACCESS_TOKEN="test-token")
    @patch("mapview.views.requests.get")
    def test_geocode_request_exception(self, mock_get):
        import requests as req

        mock_get.side_effect = req.RequestException("timeout")
        response = self.client.get(reverse("geocode"), {"q": "123 Main St"})
        self.assertEqual(response.status_code, 502)

    @override_settings(MAPBOX_ACCESS_TOKEN="test-token")
    @patch("mapview.views.requests.get")
    def test_geocode_invalid_json(self, mock_get):
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.side_effect = ValueError("bad json")
        mock_get.return_value = mock_response
        response = self.client.get(reverse("geocode"), {"q": "123 Main St"})
        self.assertEqual(response.status_code, 502)

    @override_settings(MAPBOX_ACCESS_TOKEN="test-token")
    @patch("mapview.views.requests.get")
    def test_geocode_bad_center(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "features": [{"place_name": "X", "center": []}]
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        response = self.client.get(reverse("geocode"), {"q": "123 Main St"})
        self.assertEqual(response.status_code, 502)


# ============================================================ #
#  Violations / Complaints limit edge cases
# ============================================================ #


class ViolationLimitEdgeCaseTests(TestCase):
    def test_invalid_limit_defaults_to_50(self):
        response = self.client.get(
            reverse("nta-violations"), {"nta_code": "MN01", "limit": "abc"}
        )
        self.assertEqual(response.status_code, 200)

    def test_complaint_invalid_limit_defaults_to_50(self):
        response = self.client.get(
            reverse("nta-complaints"), {"nta_code": "MN01", "limit": "abc"}
        )
        self.assertEqual(response.status_code, 200)


# ============================================================ #
#  Management Commands — compute_risk_scores
# ============================================================ #


class ComputeRiskScoresCommandTests(TestCase):
    def test_compute_scores_with_data(self):
        """compute_risk_scores runs against the actual NTA GeoJSON and DB data."""
        # Insert a violation with a known NTA code from the GeoJSON
        response = self.client.get(reverse("boundaries"), {"level": "nta"})
        payload = response.json()
        sample_code = payload["features"][0]["properties"]["nta_code"]

        HPDViolation.objects.create(
            violation_id=9001,
            violation_class="C",
            nta_code=sample_code,
            inspection_date=date(2025, 6, 1),
        )
        Complaint311.objects.create(
            unique_key="C9001",
            complaint_type="HEAT/HOT WATER",
            nta_code=sample_code,
            created_date=timezone.now(),
        )

        call_command("compute_risk_scores")

        score = NTARiskScore.objects.get(nta_code=sample_code)
        self.assertIsNotNone(score)
        self.assertGreater(score.total_violations, 0)
        self.assertLessEqual(score.risk_score, 10.0)
        self.assertGreaterEqual(score.risk_score, 0.0)

    def test_compute_scores_no_data_gives_10(self):
        """NTAs with zero violations/complaints get a score of 10."""
        response = self.client.get(reverse("boundaries"), {"level": "nta"})
        payload = response.json()
        sample_code = payload["features"][0]["properties"]["nta_code"]

        call_command("compute_risk_scores")

        score = NTARiskScore.objects.get(nta_code=sample_code)
        self.assertEqual(score.risk_score, 10.0)
        self.assertIn("Lower-risk", score.summary)

    @patch(
        "mapview.management.commands.compute_risk_scores.NTA_GEOJSON_PATH",
        Path("/nonexistent/path.geojson"),
    )
    def test_compute_scores_missing_geojson(self):
        """Command handles missing GeoJSON gracefully."""
        call_command("compute_risk_scores")
        self.assertEqual(NTARiskScore.objects.count(), 0)


# ============================================================ #
#  Management Commands — ingest_hpd_violations
# ============================================================ #


class IngestHPDViolationsCommandTests(TestCase):
    @patch("mapview.management.commands.ingest_hpd_violations.requests.get")
    def test_ingest_creates_violations(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "violationid": "100001",
                "bbl": "1234567890",
                "boroname": "MANHATTAN",
                "housenumber": "123",
                "streetname": "Main St",
                "apartment": "4A",
                "zip": "10001",
                "violationclass": "C",
                "inspectiondate": "2025-06-01T00:00:00",
                "approveddate": "2025-06-15T00:00:00",
                "novdescription": "Roach infestation",
                "novissueddate": "2025-06-02T00:00:00",
                "currentstatus": "Open",
                "currentstatusid": "1",
                "violationstatus": "Open",
                "violationstatusdate": "2025-06-01T00:00:00",
                "latitude": "40.72",
                "longitude": "-73.99",
            }
        ]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        call_command("ingest_hpd_violations", limit=10)
        self.assertEqual(HPDViolation.objects.count(), 1)
        v = HPDViolation.objects.first()
        self.assertEqual(v.violation_id, 100001)
        self.assertEqual(v.borough, "MANHATTAN")

    @patch("mapview.management.commands.ingest_hpd_violations.requests.get")
    def test_ingest_with_clear(self, mock_get):
        HPDViolation.objects.create(violation_id=1, violation_class="A")
        mock_response = MagicMock()
        mock_response.json.return_value = []
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        call_command("ingest_hpd_violations", limit=10, clear=True)
        self.assertEqual(HPDViolation.objects.count(), 0)

    @patch("mapview.management.commands.ingest_hpd_violations.requests.get")
    def test_ingest_api_failure(self, mock_get):
        import requests as req

        mock_get.side_effect = req.RequestException("API down")
        call_command("ingest_hpd_violations", limit=10)
        self.assertEqual(HPDViolation.objects.count(), 0)

    @patch("mapview.management.commands.ingest_hpd_violations.requests.get")
    def test_ingest_skips_record_without_violationid(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = [{"bbl": "123"}]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        call_command("ingest_hpd_violations", limit=10)
        self.assertEqual(HPDViolation.objects.count(), 0)

    @patch("mapview.management.commands.ingest_hpd_violations.requests.get")
    def test_ingest_updates_existing(self, mock_get):
        HPDViolation.objects.create(
            violation_id=100001, violation_class="A", borough="OLD"
        )
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "violationid": "100001",
                "boroname": "MANHATTAN",
                "violationclass": "C",
                "latitude": "40.72",
                "longitude": "-73.99",
            }
        ]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        call_command("ingest_hpd_violations", limit=10)
        self.assertEqual(HPDViolation.objects.count(), 1)
        v = HPDViolation.objects.first()
        self.assertEqual(v.borough, "MANHATTAN")


# ============================================================ #
#  Management Commands — ingest_311_complaints
# ============================================================ #


class Ingest311ComplaintsCommandTests(TestCase):
    @patch("mapview.management.commands.ingest_311_complaints.requests.get")
    def test_ingest_creates_complaints(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "unique_key": "C50001",
                "created_date": "2025-06-01T10:00:00",
                "closed_date": "2025-06-05T10:00:00",
                "agency": "HPD",
                "complaint_type": "HEAT/HOT WATER",
                "descriptor": "No heat",
                "location_type": "RESIDENTIAL BUILDING",
                "incident_address": "123 Main St",
                "incident_zip": "10001",
                "borough": "MANHATTAN",
                "status": "Closed",
                "resolution_description": "Fixed",
                "bbl": "1234567890",
                "latitude": "40.72",
                "longitude": "-73.99",
            }
        ]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        call_command("ingest_311_complaints", limit=10)
        self.assertEqual(Complaint311.objects.count(), 1)
        c = Complaint311.objects.first()
        self.assertEqual(c.unique_key, "C50001")

    @patch("mapview.management.commands.ingest_311_complaints.requests.get")
    def test_ingest_with_clear(self, mock_get):
        Complaint311.objects.create(unique_key="old", complaint_type="HEAT/HOT WATER")
        mock_response = MagicMock()
        mock_response.json.return_value = []
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        call_command("ingest_311_complaints", limit=10, clear=True)
        self.assertEqual(Complaint311.objects.count(), 0)

    @patch("mapview.management.commands.ingest_311_complaints.requests.get")
    def test_ingest_api_failure(self, mock_get):
        import requests as req

        mock_get.side_effect = req.RequestException("timeout")
        call_command("ingest_311_complaints", limit=10)
        self.assertEqual(Complaint311.objects.count(), 0)

    @patch("mapview.management.commands.ingest_311_complaints.requests.get")
    def test_ingest_skips_no_unique_key(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = [{"complaint_type": "HEAT/HOT WATER"}]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        call_command("ingest_311_complaints", limit=10)
        self.assertEqual(Complaint311.objects.count(), 0)


# ============================================================ #
#  Management Commands — ingest_all
# ============================================================ #


class IngestAllCommandTests(TestCase):
    @patch("mapview.management.commands.ingest_311_complaints.requests.get")
    @patch("mapview.management.commands.ingest_hpd_violations.requests.get")
    def test_ingest_all_runs_pipeline(self, mock_hpd_get, mock_311_get):
        mock_hpd_resp = MagicMock()
        mock_hpd_resp.json.return_value = []
        mock_hpd_resp.raise_for_status.return_value = None
        mock_hpd_get.return_value = mock_hpd_resp

        mock_311_resp = MagicMock()
        mock_311_resp.json.return_value = []
        mock_311_resp.raise_for_status.return_value = None
        mock_311_get.return_value = mock_311_resp

        call_command("ingest_all", limit=5)
        # If no exceptions, the pipeline ran successfully


# ============================================================ #
#  Sprint 3 – Ingestion Models
# ============================================================ #


class IngestionJobModelTests(TestCase):
    def test_create_job(self):
        job = IngestionJob.objects.create(
            trigger_type=IngestionJob.TRIGGER_MANUAL,
            requested_limit=10000,
            sources=IngestionJob.SOURCE_BOTH,
        )
        self.assertEqual(job.status, IngestionJob.STATUS_PENDING)
        self.assertIn("Pending", str(job))

    def test_is_running(self):
        job = IngestionJob.objects.create(
            trigger_type=IngestionJob.TRIGGER_MANUAL,
            status=IngestionJob.STATUS_RUNNING,
            started_at=timezone.now(),
        )
        self.assertTrue(job.is_running)

    def test_elapsed_seconds(self):
        job = IngestionJob.objects.create(
            trigger_type=IngestionJob.TRIGGER_MANUAL,
            status=IngestionJob.STATUS_RUNNING,
            started_at=timezone.now(),
        )
        self.assertGreaterEqual(job.elapsed_seconds, 0)

    def test_ordering_latest_first(self):
        IngestionJob.objects.create(trigger_type=IngestionJob.TRIGGER_MANUAL)
        j2 = IngestionJob.objects.create(trigger_type=IngestionJob.TRIGGER_SCHEDULED)
        first = IngestionJob.objects.first()
        self.assertEqual(first.pk, j2.pk)


class IngestionScheduleModelTests(TestCase):
    def test_singleton_load(self):
        s1 = IngestionSchedule.load()
        s2 = IngestionSchedule.load()
        self.assertEqual(s1.pk, s2.pk)

    def test_defaults(self):
        s = IngestionSchedule.load()
        self.assertFalse(s.is_enabled)
        self.assertEqual(s.interval_unit, "days")


class ScoreRecencyConfigModelTests(TestCase):
    def test_singleton_load(self):
        c1 = ScoreRecencyConfig.load()
        c2 = ScoreRecencyConfig.load()
        self.assertEqual(c1.pk, c2.pk)

    def test_default_is_all(self):
        c = ScoreRecencyConfig.load()
        self.assertEqual(c.recency_window, "all")


# ============================================================ #
#  Sprint 3 – Ingestion API Endpoints
# ============================================================ #


class IngestionAPITestMixin:
    """Helper to create an admin user and log in."""

    def _login_admin(self):
        self.admin = User.objects.create_superuser(
            username="ingadmin", password="StrongPass99!", email="a@test.com"
        )
        self.client.login(username="ingadmin", password="StrongPass99!")


class IngestionStatusAPITests(IngestionAPITestMixin, TestCase):
    def test_unauthenticated_returns_401(self):
        response = self.client.get(reverse("ingestion-status"))
        self.assertEqual(response.status_code, 401)

    def test_non_admin_returns_403(self):
        User.objects.create_user(username="pub", password="StrongPass99!")
        self.client.login(username="pub", password="StrongPass99!")
        response = self.client.get(reverse("ingestion-status"))
        self.assertEqual(response.status_code, 403)

    def test_idle_status(self):
        self._login_admin()
        response = self.client.get(reverse("ingestion-status"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "idle")

    def test_running_status(self):
        self._login_admin()
        IngestionJob.objects.create(
            trigger_type=IngestionJob.TRIGGER_MANUAL,
            status=IngestionJob.STATUS_RUNNING,
            started_at=timezone.now(),
        )
        response = self.client.get(reverse("ingestion-status"))
        data = response.json()
        self.assertEqual(data["status"], "running")


class IngestionStatsAPITests(IngestionAPITestMixin, TestCase):
    def test_stats_returns_counts(self):
        self._login_admin()
        HPDViolation.objects.create(violation_id=1, violation_class="A")
        Complaint311.objects.create(unique_key="C1", complaint_type="HEAT/HOT WATER")
        response = self.client.get(reverse("ingestion-stats"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["hpd_violations"], 1)
        self.assertEqual(data["complaints_311"], 1)
        self.assertIn("recency_window", data)


class IngestionHistoryAPITests(IngestionAPITestMixin, TestCase):
    def test_empty_history(self):
        self._login_admin()
        response = self.client.get(reverse("ingestion-history"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["history"]), 0)

    def test_history_returns_jobs(self):
        self._login_admin()
        IngestionJob.objects.create(
            trigger_type=IngestionJob.TRIGGER_MANUAL,
            status=IngestionJob.STATUS_COMPLETED,
        )
        response = self.client.get(reverse("ingestion-history"))
        data = response.json()
        self.assertEqual(len(data["history"]), 1)


class IngestionScheduleAPITests(IngestionAPITestMixin, TestCase):
    def test_get_schedule(self):
        self._login_admin()
        response = self.client.get(reverse("ingestion-schedule"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("is_enabled", data)

    def test_update_schedule(self):
        self._login_admin()
        response = self.client.post(
            reverse("ingestion-schedule"),
            json.dumps(
                {"is_enabled": True, "interval_value": 3, "interval_unit": "days"}
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["is_enabled"])
        self.assertEqual(data["interval_value"], 3)


class IngestionRecencyAPITests(IngestionAPITestMixin, TestCase):
    def test_get_recency(self):
        self._login_admin()
        response = self.client.get(reverse("ingestion-recency"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["recency_window"], "all")

    def test_set_invalid_recency(self):
        self._login_admin()
        response = self.client.post(
            reverse("ingestion-recency"),
            json.dumps({"recency_window": "invalid"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_set_valid_recency(self):
        self._login_admin()
        response = self.client.post(
            reverse("ingestion-recency"),
            json.dumps({"recency_window": "6m"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        config = ScoreRecencyConfig.load()
        self.assertEqual(config.recency_window, "6m")


class IngestionStartAPITests(IngestionAPITestMixin, TestCase):
    @patch("mapview.views_ingestion.run_ingestion_job")
    def test_start_creates_job(self, mock_run):
        self._login_admin()
        response = self.client.post(
            reverse("ingestion-start"),
            json.dumps({"limit": 5000, "sources": "hpd_only"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("job", data)
        self.assertEqual(data["job"]["sources"], "hpd_only")
        mock_run.assert_called_once()


# ============================================================ #
#  Sprint 3 – Map-Community API Endpoints
# ============================================================ #


class MapRecencyLabelTests(TestCase):
    def test_recency_label_returns_200(self):
        response = self.client.get(reverse("map-recency-label"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("label", data)


class MapMyMarkerTests(TestCase):
    def test_unauthenticated_returns_no_marker(self):
        response = self.client.get(reverse("map-my-marker"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data["has_marker"])


class MapCommunityPreviewTests(TestCase):
    def test_unknown_nta_returns_404(self):
        response = self.client.get(reverse("map-community-preview", args=["ZZZZZ"]))
        self.assertEqual(response.status_code, 404)

    def test_nta_without_community(self):
        NTARiskScore.objects.create(
            nta_code="TEST01", nta_name="Test NTA", borough="TEST"
        )
        response = self.client.get(reverse("map-community-preview", args=["TEST01"]))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data["has_community"])


class MapCommunityActivityTests(TestCase):
    def test_activity_returns_200(self):
        response = self.client.get(reverse("map-community-activity"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("communities", data)


# ============================================================ #
#  Sprint 3 – Ingestion Dashboard View
# ============================================================ #


class IngestionDashboardViewTests(TestCase):
    def test_anonymous_redirected(self):
        response = self.client.get(reverse("ingestion-dashboard"))
        self.assertEqual(response.status_code, 302)

    def test_non_admin_redirected(self):
        User.objects.create_user(username="pub", password="StrongPass99!")
        self.client.login(username="pub", password="StrongPass99!")
        response = self.client.get(reverse("ingestion-dashboard"))
        self.assertEqual(response.status_code, 302)

    def test_admin_can_access(self):
        User.objects.create_superuser(
            username="admin", password="StrongPass99!", email="a@t.com"
        )
        self.client.login(username="admin", password="StrongPass99!")
        response = self.client.get(reverse("ingestion-dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Data Ingestion Dashboard")


# ============================================================ #
#  Epic #5 – Risk Score History
# ============================================================ #


class RiskScoreHistoryModelTests(TestCase):
    def test_create_history(self):
        h = RiskScoreHistory.objects.create(
            nta_code="MN01",
            nta_name="Test",
            risk_score=7.0,
            previous_score=8.0,
            score_delta=-1.0,
        )
        self.assertIn("MN01", str(h))
        self.assertIn("-1.0", str(h))

    def test_history_ordering(self):
        RiskScoreHistory.objects.create(nta_code="MN01", nta_name="A", risk_score=5.0)
        RiskScoreHistory.objects.create(nta_code="MN01", nta_name="A", risk_score=6.0)
        latest = RiskScoreHistory.objects.first()
        self.assertEqual(latest.risk_score, 6.0)


class RiskHistoryAPITests(TestCase):
    def test_history_requires_nta_code(self):
        response = self.client.get(reverse("risk-history"))
        self.assertEqual(response.status_code, 400)

    def test_history_returns_records(self):
        RiskScoreHistory.objects.create(
            nta_code="MN01", nta_name="Test", risk_score=7.0
        )
        response = self.client.get(reverse("risk-history"), {"nta_code": "MN01"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 1)

    def test_risk_changes_endpoint(self):
        RiskScoreHistory.objects.create(
            nta_code="MN01",
            nta_name="Test",
            risk_score=6.0,
            previous_score=8.0,
            score_delta=-2.0,
        )
        response = self.client.get(reverse("risk-changes"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertGreaterEqual(data["count"], 1)


# ============================================================ #
#  Epic #7 – Scheduled Ingestion Command
# ============================================================ #


class RunScheduledIngestionTests(TestCase):
    def test_disabled_schedule_does_nothing(self):
        schedule = IngestionSchedule.load()
        schedule.is_enabled = False
        schedule.save()
        call_command("run_scheduled_ingestion")
        self.assertEqual(
            IngestionJob.objects.filter(
                trigger_type=IngestionJob.TRIGGER_SCHEDULED
            ).count(),
            0,
        )

    def test_not_due_does_nothing(self):
        from datetime import timedelta

        schedule = IngestionSchedule.load()
        schedule.is_enabled = True
        schedule.next_run_at = timezone.now() + timedelta(hours=1)
        schedule.save()
        call_command("run_scheduled_ingestion")
        self.assertEqual(
            IngestionJob.objects.filter(
                trigger_type=IngestionJob.TRIGGER_SCHEDULED
            ).count(),
            0,
        )

    @patch("mapview.management.commands.run_scheduled_ingestion.run_ingestion_job")
    @patch(
        "mapview.management.commands.run_scheduled_ingestion.is_job_running",
        return_value=False,
    )
    def test_due_schedule_creates_job(self, mock_running, mock_run):
        from datetime import timedelta

        schedule = IngestionSchedule.load()
        schedule.is_enabled = True
        schedule.next_run_at = timezone.now() - timedelta(minutes=5)
        schedule.save()
        call_command("run_scheduled_ingestion")
        self.assertEqual(
            IngestionJob.objects.filter(
                trigger_type=IngestionJob.TRIGGER_SCHEDULED
            ).count(),
            1,
        )
        mock_run.assert_called_once()
        schedule.refresh_from_db()
        self.assertIsNotNone(schedule.next_run_at)
        self.assertIsNotNone(schedule.last_run_at)


# ============================================================ #
#  Epic #8 – Area Subscriptions & Notifications
# ============================================================ #


class AreaSubscriptionModelTests(TestCase):
    def test_create_subscription(self):
        user = User.objects.create_user(username="sub1", password="StrongPass99!")
        sub = AreaSubscription.objects.create(
            user=user, nta_code="MN01", nta_name="Test"
        )
        self.assertIn("sub1", str(sub))
        self.assertTrue(sub.is_active)

    def test_unique_together(self):
        user = User.objects.create_user(username="sub2", password="StrongPass99!")
        AreaSubscription.objects.create(user=user, nta_code="MN01")
        from django.db import IntegrityError

        with self.assertRaises(IntegrityError):
            AreaSubscription.objects.create(user=user, nta_code="MN01")


class NotificationModelTests(TestCase):
    def test_create_notification(self):
        user = User.objects.create_user(username="notif1", password="StrongPass99!")
        n = Notification.objects.create(user=user, title="Test", message="Hello")
        self.assertFalse(n.is_read)
        self.assertIn("notif1", str(n))


class SubscriptionAPITests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="subapi", password="StrongPass99!", email="s@t.com"
        )

    def test_list_unauthenticated(self):
        response = self.client.get(reverse("subscription-list"))
        self.assertEqual(response.status_code, 401)

    def test_list_empty(self):
        self.client.login(username="subapi", password="StrongPass99!")
        response = self.client.get(reverse("subscription-list"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["subscriptions"]), 0)

    def test_create_subscription(self):
        self.client.login(username="subapi", password="StrongPass99!")
        response = self.client.post(
            reverse("subscription-create"),
            json.dumps({"nta_code": "MN01", "delivery_method": "email"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["nta_code"], "MN01")
        self.assertTrue(data["created"])

    def test_create_subscription_requires_nta(self):
        self.client.login(username="subapi", password="StrongPass99!")
        response = self.client.post(
            reverse("subscription-create"),
            json.dumps({}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_update_subscription(self):
        self.client.login(username="subapi", password="StrongPass99!")
        sub = AreaSubscription.objects.create(
            user=self.user, nta_code="MN01", nta_name="Test"
        )
        response = self.client.post(
            reverse("subscription-update", args=[sub.pk]),
            json.dumps({"is_active": False}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["is_active"])

    def test_delete_subscription(self):
        self.client.login(username="subapi", password="StrongPass99!")
        sub = AreaSubscription.objects.create(user=self.user, nta_code="MN01")
        response = self.client.delete(reverse("subscription-update", args=[sub.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(AreaSubscription.objects.filter(pk=sub.pk).exists())


class NotificationAPITests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="notifapi", password="StrongPass99!"
        )

    def test_list_unauthenticated(self):
        response = self.client.get(reverse("notification-list"))
        self.assertEqual(response.status_code, 401)

    def test_list_notifications(self):
        self.client.login(username="notifapi", password="StrongPass99!")
        Notification.objects.create(
            user=self.user, title="Alert", message="Score changed"
        )
        response = self.client.get(reverse("notification-list"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["notifications"]), 1)
        self.assertEqual(data["unread_count"], 1)

    def test_mark_read(self):
        self.client.login(username="notifapi", password="StrongPass99!")
        n = Notification.objects.create(
            user=self.user, title="Alert", message="Score changed"
        )
        response = self.client.post(reverse("notification-read", args=[n.pk]))
        self.assertEqual(response.status_code, 200)
        n.refresh_from_db()
        self.assertTrue(n.is_read)

    def test_mark_all_read(self):
        self.client.login(username="notifapi", password="StrongPass99!")
        Notification.objects.create(user=self.user, title="A1", message="m")
        Notification.objects.create(user=self.user, title="A2", message="m")
        response = self.client.post(reverse("notification-read-all"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            Notification.objects.filter(user=self.user, is_read=False).count(),
            0,
        )

    def test_unread_filter(self):
        self.client.login(username="notifapi", password="StrongPass99!")
        Notification.objects.create(
            user=self.user, title="Read", message="m", is_read=True
        )
        Notification.objects.create(
            user=self.user, title="Unread", message="m", is_read=False
        )
        response = self.client.get(reverse("notification-list"), {"unread": "true"})
        data = response.json()
        self.assertEqual(len(data["notifications"]), 1)
        self.assertEqual(data["notifications"][0]["title"], "Unread")


class RiskChangeAlertTests(TestCase):
    def test_alerts_created_on_score_change(self):
        from mapview.ingestion import _send_risk_change_alerts

        user = User.objects.create_user(
            username="alertuser", password="StrongPass99!", email="a@t.com"
        )
        job = IngestionJob.objects.create(
            trigger_type=IngestionJob.TRIGGER_MANUAL,
            status=IngestionJob.STATUS_COMPLETED,
        )
        RiskScoreHistory.objects.create(
            nta_code="MN01",
            nta_name="Test NTA",
            risk_score=5.0,
            previous_score=7.0,
            score_delta=-2.0,
            ingestion_job=job,
        )
        AreaSubscription.objects.create(
            user=user,
            nta_code="MN01",
            delivery_method=AreaSubscription.DELIVERY_IN_APP,
            threshold=0.5,
        )

        _send_risk_change_alerts(job)

        self.assertEqual(Notification.objects.filter(user=user).count(), 1)
        notif = Notification.objects.get(user=user)
        self.assertIn("worsened", notif.title)

    def test_no_alert_below_threshold(self):
        from mapview.ingestion import _send_risk_change_alerts

        user = User.objects.create_user(username="alertuser2", password="StrongPass99!")
        job = IngestionJob.objects.create(
            trigger_type=IngestionJob.TRIGGER_MANUAL,
            status=IngestionJob.STATUS_COMPLETED,
        )
        RiskScoreHistory.objects.create(
            nta_code="MN02",
            nta_name="Test2",
            risk_score=7.1,
            previous_score=7.0,
            score_delta=0.1,
            ingestion_job=job,
        )
        AreaSubscription.objects.create(
            user=user,
            nta_code="MN02",
            threshold=0.5,
        )

        _send_risk_change_alerts(job)

        self.assertEqual(Notification.objects.filter(user=user).count(), 0)


# ============================================================ #
#  Epic #9 – Landlord Portfolio
# ============================================================ #


class LandlordSearchTests(TestCase):
    def test_search_requires_query(self):
        response = self.client.get(reverse("landlord-search"))
        self.assertEqual(response.status_code, 400)

    def test_search_short_query(self):
        response = self.client.get(reverse("landlord-search"), {"q": "ab"})
        self.assertEqual(response.status_code, 400)

    def test_search_by_street(self):
        HPDViolation.objects.create(
            violation_id=5001,
            bbl="1000010001",
            house_number="100",
            street_name="BROADWAY",
            borough="MANHATTAN",
            zip_code="10001",
            violation_class="B",
        )
        response = self.client.get(reverse("landlord-search"), {"q": "BROADWAY"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertGreaterEqual(data["count"], 1)
        self.assertEqual(data["buildings"][0]["bbl"], "1000010001")

    def test_search_with_borough_filter(self):
        HPDViolation.objects.create(
            violation_id=5002,
            bbl="2000010001",
            house_number="200",
            street_name="GRAND CONCOURSE",
            borough="BRONX",
            violation_class="A",
        )
        response = self.client.get(
            reverse("landlord-search"),
            {"q": "GRAND", "borough": "BRONX"},
        )
        data = response.json()
        self.assertGreaterEqual(data["count"], 1)


class BuildingPortfolioTests(TestCase):
    def test_requires_bbl(self):
        response = self.client.get(reverse("building-portfolio"))
        self.assertEqual(response.status_code, 400)

    def test_building_details(self):
        HPDViolation.objects.create(
            violation_id=6001,
            bbl="1000010001",
            house_number="100",
            street_name="BROADWAY",
            borough="MANHATTAN",
            zip_code="10001",
            violation_class="C",
        )
        HPDViolation.objects.create(
            violation_id=6002,
            bbl="1000010001",
            house_number="100",
            street_name="BROADWAY",
            borough="MANHATTAN",
            zip_code="10001",
            violation_class="A",
        )
        Complaint311.objects.create(
            unique_key="C6001",
            bbl="1000010001",
            complaint_type="HEAT/HOT WATER",
        )
        response = self.client.get(reverse("building-portfolio"), {"bbl": "1000010001"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["summary"]["total_violations"], 2)
        self.assertEqual(data["summary"]["total_complaints"], 1)
        self.assertEqual(data["summary"]["class_c_violations"], 1)

    def test_empty_building(self):
        response = self.client.get(reverse("building-portfolio"), {"bbl": "9999999999"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["summary"]["total_violations"], 0)


class LandlordPortfolioTests(TestCase):
    def test_requires_bbl(self):
        response = self.client.get(reverse("landlord-portfolio"))
        self.assertEqual(response.status_code, 400)

    def test_short_bbl_rejected(self):
        response = self.client.get(reverse("landlord-portfolio"), {"bbl": "123"})
        self.assertEqual(response.status_code, 400)

    def test_portfolio_aggregates_related_buildings(self):
        HPDViolation.objects.create(
            violation_id=7001,
            bbl="1000010001",
            house_number="100",
            street_name="BROADWAY",
            borough="MANHATTAN",
            violation_class="B",
        )
        HPDViolation.objects.create(
            violation_id=7002,
            bbl="1000010002",
            house_number="102",
            street_name="BROADWAY",
            borough="MANHATTAN",
            violation_class="C",
        )
        response = self.client.get(reverse("landlord-portfolio"), {"bbl": "1000010001"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["building_count"], 2)
        self.assertEqual(data["total_violations"], 2)

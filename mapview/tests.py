from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Complaint311, HPDViolation, NTARiskScore, ScoreThreshold

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

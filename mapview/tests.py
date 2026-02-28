from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings
from django.urls import reverse


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

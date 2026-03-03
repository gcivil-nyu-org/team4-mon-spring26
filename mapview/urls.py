from django.urls import path

from .views import (
    boundary_geojson_view,
    dashboard_view,
    geocode_view,
    nta_complaints_view,
    nta_geojson_view,
    nta_risk_summary_view,
    nta_violations_view,
)

urlpatterns = [
    path("", dashboard_view, name="dashboard"),
    path("api/nta-geojson/", nta_geojson_view, name="nta-geojson"),
    path("api/boundaries/", boundary_geojson_view, name="boundaries"),
    path("api/geocode/", geocode_view, name="geocode"),
    path("api/nta-violations/", nta_violations_view, name="nta-violations"),
    path("api/nta-complaints/", nta_complaints_view, name="nta-complaints"),
    path("api/nta-risk-summary/", nta_risk_summary_view, name="nta-risk-summary"),
]

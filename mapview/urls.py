from django.urls import path

from .views import (
    boundary_geojson_view,
    dashboard_view,
    geocode_view,
    ingestion_dashboard_view,
    nta_complaints_view,
    nta_geojson_view,
    nta_risk_summary_view,
    nta_violations_view,
)
from .views_ingestion import (
    ingestion_history_view,
    ingestion_recency_view,
    ingestion_schedule_view,
    ingestion_start_view,
    ingestion_stats_view,
    ingestion_status_view,
)
from .views_landlord import (
    building_portfolio_view,
    landlord_portfolio_view,
    landlord_search_view,
)
from .views_map_community import (
    community_activity_view,
    community_preview_view,
    my_marker_view,
    recency_label_view,
)
from .views_subscription import (
    notification_list_view,
    notification_read_all_view,
    notification_read_view,
    risk_changes_view,
    risk_history_view,
    subscription_create_view,
    subscription_list_view,
    subscription_update_view,
)
from .views_health import health_check_view

urlpatterns = [
    path("health/", health_check_view, name="health-check"),
    path("", dashboard_view, name="dashboard"),
    path("ingestion-dashboard/", ingestion_dashboard_view, name="ingestion-dashboard"),
    path("api/nta-geojson/", nta_geojson_view, name="nta-geojson"),
    path("api/boundaries/", boundary_geojson_view, name="boundaries"),
    path("api/geocode/", geocode_view, name="geocode"),
    path("api/nta-violations/", nta_violations_view, name="nta-violations"),
    path("api/nta-complaints/", nta_complaints_view, name="nta-complaints"),
    path("api/nta-risk-summary/", nta_risk_summary_view, name="nta-risk-summary"),
    # Ingestion API (admin-only)
    path("api/ingestion/status/", ingestion_status_view, name="ingestion-status"),
    path("api/ingestion/start/", ingestion_start_view, name="ingestion-start"),
    path("api/ingestion/history/", ingestion_history_view, name="ingestion-history"),
    path("api/ingestion/stats/", ingestion_stats_view, name="ingestion-stats"),
    path(
        "api/ingestion/schedule/",
        ingestion_schedule_view,
        name="ingestion-schedule",
    ),
    path("api/ingestion/recency/", ingestion_recency_view, name="ingestion-recency"),
    # Map-Community API
    path(
        "api/map/community-preview/<str:nta_code>/",
        community_preview_view,
        name="map-community-preview",
    ),
    path(
        "api/map/community-activity/",
        community_activity_view,
        name="map-community-activity",
    ),
    path("api/map/my-marker/", my_marker_view, name="map-my-marker"),
    path("api/map/recency-label/", recency_label_view, name="map-recency-label"),
    # Risk History (Epic #5)
    path("api/risk-history/", risk_history_view, name="risk-history"),
    path("api/risk-changes/", risk_changes_view, name="risk-changes"),
    # Subscriptions & Notifications (Epic #8)
    path(
        "api/subscriptions/",
        subscription_list_view,
        name="subscription-list",
    ),
    path(
        "api/subscriptions/create/",
        subscription_create_view,
        name="subscription-create",
    ),
    path(
        "api/subscriptions/<int:pk>/",
        subscription_update_view,
        name="subscription-update",
    ),
    path(
        "api/notifications/",
        notification_list_view,
        name="notification-list",
    ),
    path(
        "api/notifications/<int:pk>/read/",
        notification_read_view,
        name="notification-read",
    ),
    path(
        "api/notifications/read-all/",
        notification_read_all_view,
        name="notification-read-all",
    ),
    # Landlord Portfolio (Epic #9)
    path("api/landlord/search/", landlord_search_view, name="landlord-search"),
    path(
        "api/landlord/building/",
        building_portfolio_view,
        name="building-portfolio",
    ),
    path(
        "api/landlord/portfolio/",
        landlord_portfolio_view,
        name="landlord-portfolio",
    ),
]

from django.contrib import admin

from .models import Complaint311, HPDViolation, NTARiskScore, ScoreThreshold


@admin.register(HPDViolation)
class HPDViolationAdmin(admin.ModelAdmin):
    list_display = [
        "violation_id",
        "borough",
        "address",
        "violation_class",
        "inspection_date",
        "nta_code",
    ]
    list_filter = ["violation_class", "borough"]
    search_fields = ["house_number", "street_name", "nta_code"]
    readonly_fields = ["ingested_at"]


@admin.register(Complaint311)
class Complaint311Admin(admin.ModelAdmin):
    list_display = [
        "unique_key",
        "complaint_type",
        "borough",
        "status",
        "created_date",
        "nta_code",
    ]
    list_filter = ["complaint_type", "borough", "status"]
    search_fields = ["incident_address", "unique_key", "nta_code"]
    readonly_fields = ["ingested_at"]


@admin.register(NTARiskScore)
class NTARiskScoreAdmin(admin.ModelAdmin):
    list_display = [
        "nta_code",
        "nta_name",
        "borough",
        "risk_score",
        "total_violations",
        "total_complaints",
    ]
    list_filter = ["borough"]
    search_fields = ["nta_code", "nta_name"]
    readonly_fields = ["last_updated"]


@admin.register(ScoreThreshold)
class ScoreThresholdAdmin(admin.ModelAdmin):
    list_display = ["name", "max_score", "color"]
    ordering = ["max_score"]

from django.contrib import admin

from .models import (
    Complaint311,
    HPDViolation,
    IngestionJob,
    IngestionSchedule,
    NTARiskScore,
    ScoreRecencyConfig,
    ScoreThreshold,
)


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


@admin.register(IngestionJob)
class IngestionJobAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "status",
        "trigger_type",
        "sources",
        "requested_limit",
        "started_at",
        "completed_at",
    ]
    list_filter = ["status", "trigger_type"]
    readonly_fields = ["created_at"]


@admin.register(IngestionSchedule)
class IngestionScheduleAdmin(admin.ModelAdmin):
    list_display = [
        "is_enabled",
        "interval_value",
        "interval_unit",
        "run_time",
        "last_run_at",
        "next_run_at",
    ]


@admin.register(ScoreRecencyConfig)
class ScoreRecencyConfigAdmin(admin.ModelAdmin):
    list_display = ["recency_window", "last_recomputed_at", "updated_at"]

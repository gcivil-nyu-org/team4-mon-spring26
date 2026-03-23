from django.db import models


class HPDViolation(models.Model):
    """HPD housing violation records from NYC Open Data."""

    violation_id = models.IntegerField(unique=True, db_index=True)
    bbl = models.CharField(max_length=15, db_index=True, blank=True, default="")
    borough = models.CharField(max_length=20, blank=True, default="")
    house_number = models.CharField(max_length=20, blank=True, default="")
    street_name = models.CharField(max_length=100, blank=True, default="")
    apartment = models.CharField(max_length=20, blank=True, default="")
    zip_code = models.CharField(max_length=10, blank=True, default="")
    violation_class = models.CharField(max_length=5, db_index=True)
    inspection_date = models.DateField(null=True, blank=True)
    approved_date = models.DateField(null=True, blank=True)
    nov_description = models.TextField(blank=True, default="")
    nov_issued_date = models.DateField(null=True, blank=True)
    current_status = models.CharField(max_length=50, blank=True, default="")
    current_status_id = models.IntegerField(null=True, blank=True)
    violation_status = models.CharField(max_length=50, blank=True, default="")
    violation_status_date = models.DateField(null=True, blank=True)
    nta_code = models.CharField(max_length=10, blank=True, default="", db_index=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    ingested_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-inspection_date"]
        verbose_name = "HPD Violation"
        verbose_name_plural = "HPD Violations"

    def __str__(self):
        return f"HPD-{self.violation_id} (Class {self.violation_class}) {self.address}"

    @property
    def address(self):
        return f"{self.house_number} {self.street_name}".strip()


class Complaint311(models.Model):
    """311 complaint records related to housing from NYC Open Data."""

    unique_key = models.CharField(max_length=20, unique=True, db_index=True)
    created_date = models.DateTimeField(null=True, blank=True)
    closed_date = models.DateTimeField(null=True, blank=True)
    agency = models.CharField(max_length=20, blank=True, default="")
    complaint_type = models.CharField(max_length=100, db_index=True)
    descriptor = models.CharField(max_length=255, blank=True, default="")
    location_type = models.CharField(max_length=100, blank=True, default="")
    incident_address = models.CharField(max_length=255, blank=True, default="")
    incident_zip = models.CharField(max_length=10, blank=True, default="")
    borough = models.CharField(max_length=20, blank=True, default="")
    status = models.CharField(max_length=50, blank=True, default="")
    resolution_description = models.TextField(blank=True, default="")
    bbl = models.CharField(max_length=15, blank=True, default="", db_index=True)
    nta_code = models.CharField(max_length=10, blank=True, default="", db_index=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    ingested_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_date"]
        verbose_name = "311 Complaint"
        verbose_name_plural = "311 Complaints"

    def __str__(self):
        return f"311-{self.unique_key}: {self.complaint_type}"


class NTARiskScore(models.Model):
    """Pre-computed risk scores per NTA neighborhood."""

    nta_code = models.CharField(max_length=10, unique=True, db_index=True)
    nta_name = models.CharField(max_length=100)
    borough = models.CharField(max_length=20)
    total_violations = models.IntegerField(default=0)
    total_complaints = models.IntegerField(default=0)
    class_a_violations = models.IntegerField(default=0)
    class_b_violations = models.IntegerField(default=0)
    class_c_violations = models.IntegerField(default=0)
    risk_score = models.FloatField(default=5.0)
    top_complaint_types = models.JSONField(default=list)
    summary = models.TextField(blank=True, default="")
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "NTA Risk Score"
        verbose_name_plural = "NTA Risk Scores"
        ordering = ["risk_score"]

    def __str__(self):
        return f"{self.nta_name} ({self.nta_code}): {self.risk_score}/10"


class ScoreThreshold(models.Model):
    """Configurable thresholds for map coloration."""

    name = models.CharField(
        max_length=50, help_text="e.g. 'High Risk', 'Medium Risk', 'Low Risk'"
    )
    color = models.CharField(max_length=20, help_text="Hex color code (e.g., #dc2626)")
    max_score = models.FloatField(
        help_text="Maximum score for this color. Ordered lowest to highest."
    )

    class Meta:
        ordering = ["max_score"]
        verbose_name = "Score Threshold"
        verbose_name_plural = "Score Thresholds"

    def __str__(self):
        return f"{self.name} (<= {self.max_score}): {self.color}"

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


class IngestionJob(models.Model):
    """Tracks each data ingestion run (manual or scheduled)."""

    STATUS_PENDING = "pending"
    STATUS_RUNNING = "running"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_RUNNING, "Running"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_FAILED, "Failed"),
    ]

    TRIGGER_MANUAL = "manual"
    TRIGGER_SCHEDULED = "scheduled"
    TRIGGER_CHOICES = [
        (TRIGGER_MANUAL, "Manual"),
        (TRIGGER_SCHEDULED, "Scheduled"),
    ]

    SOURCE_BOTH = "both"
    SOURCE_HPD = "hpd_only"
    SOURCE_311 = "311_only"
    SOURCE_CHOICES = [
        (SOURCE_BOTH, "Both"),
        (SOURCE_HPD, "HPD Only"),
        (SOURCE_311, "311 Only"),
    ]

    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True
    )
    trigger_type = models.CharField(
        max_length=20, choices=TRIGGER_CHOICES, default=TRIGGER_MANUAL
    )
    requested_limit = models.IntegerField(default=10000)
    sources = models.CharField(
        max_length=50, choices=SOURCE_CHOICES, default=SOURCE_BOTH
    )
    current_step = models.CharField(max_length=100, blank=True, default="")
    records_fetched = models.IntegerField(default=0)
    records_target = models.IntegerField(default=0)
    current_batch = models.IntegerField(default=0)
    total_batches = models.IntegerField(default=0)
    hpd_created = models.IntegerField(default=0)
    hpd_updated = models.IntegerField(default=0)
    complaints_created = models.IntegerField(default=0)
    complaints_updated = models.IntegerField(default=0)
    neighborhoods_scored = models.IntegerField(default=0)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Ingestion Job"
        verbose_name_plural = "Ingestion Jobs"

    def __str__(self):
        return (
            f"Ingestion #{self.pk} [{self.get_status_display()}] "
            f"({self.get_trigger_type_display()})"
        )

    @property
    def is_running(self):
        return self.status == self.STATUS_RUNNING

    @property
    def elapsed_seconds(self):
        if not self.started_at:
            return 0
        from django.utils import timezone

        end = self.completed_at or timezone.now()
        return (end - self.started_at).total_seconds()


class IngestionSchedule(models.Model):
    """Singleton — configures automatic recurring data ingestion."""

    UNIT_HOURS = "hours"
    UNIT_DAYS = "days"
    UNIT_CHOICES = [
        (UNIT_HOURS, "Hours"),
        (UNIT_DAYS, "Days"),
    ]

    is_enabled = models.BooleanField(default=False)
    interval_value = models.IntegerField(default=7)
    interval_unit = models.CharField(
        max_length=10, choices=UNIT_CHOICES, default=UNIT_DAYS
    )
    run_time = models.TimeField(default="03:00", help_text="Scheduled run time in UTC")
    record_limit = models.IntegerField(default=10000)
    sources = models.CharField(
        max_length=50,
        choices=IngestionJob.SOURCE_CHOICES,
        default=IngestionJob.SOURCE_BOTH,
    )
    last_run_at = models.DateTimeField(null=True, blank=True)
    next_run_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Ingestion Schedule"
        verbose_name_plural = "Ingestion Schedules"

    def __str__(self):
        state = "Enabled" if self.is_enabled else "Disabled"
        return f"Schedule: every {self.interval_value} {self.interval_unit} [{state}]"

    @classmethod
    def load(cls):
        """Return the singleton schedule, creating it if needed."""
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class ScoreRecencyConfig(models.Model):
    """Singleton — controls the time window for risk score computation."""

    RECENCY_CHOICES = [
        ("1m", "Last 1 month"),
        ("3m", "Last 3 months"),
        ("6m", "Last 6 months"),
        ("1y", "Last 1 year"),
        ("2y", "Last 2 years"),
        ("all", "All time"),
    ]

    recency_window = models.CharField(
        max_length=5, choices=RECENCY_CHOICES, default="all"
    )
    last_recomputed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Score Recency Config"
        verbose_name_plural = "Score Recency Configs"

    def __str__(self):
        return f"Recency: {self.get_recency_window_display()}"

    @classmethod
    def load(cls):
        """Return the singleton config, creating it if needed."""
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def get_cutoff_date(self):
        """Return the datetime cutoff for the configured window, or None for 'all'."""
        if self.recency_window == "all":
            return None
        from django.utils import timezone
        from dateutil.relativedelta import relativedelta

        now = timezone.now()
        mapping = {
            "1m": relativedelta(months=1),
            "3m": relativedelta(months=3),
            "6m": relativedelta(months=6),
            "1y": relativedelta(years=1),
            "2y": relativedelta(years=2),
        }
        delta = mapping.get(self.recency_window)
        return (now - delta) if delta else None


class RiskScoreHistory(models.Model):
    """Snapshot of an NTA risk score at a point in time."""

    nta_code = models.CharField(max_length=10, db_index=True)
    nta_name = models.CharField(max_length=100)
    risk_score = models.FloatField()
    previous_score = models.FloatField(null=True, blank=True)
    score_delta = models.FloatField(default=0.0)
    total_violations = models.IntegerField(default=0)
    total_complaints = models.IntegerField(default=0)
    ingestion_job = models.ForeignKey(
        IngestionJob,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="score_history",
    )
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-recorded_at"]
        verbose_name = "Risk Score History"
        verbose_name_plural = "Risk Score Histories"
        indexes = [
            models.Index(fields=["nta_code", "-recorded_at"]),
        ]

    def __str__(self):
        return f"{self.nta_code} {self.risk_score}/10 ({self.score_delta:+.1f})"


class AreaSubscription(models.Model):
    """User subscription to risk alerts for a specific NTA area."""

    DELIVERY_EMAIL = "email"
    DELIVERY_IN_APP = "in_app"
    DELIVERY_BOTH = "both"
    DELIVERY_CHOICES = [
        (DELIVERY_EMAIL, "Email"),
        (DELIVERY_IN_APP, "In-App"),
        (DELIVERY_BOTH, "Both"),
    ]

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="area_subscriptions",
    )
    nta_code = models.CharField(max_length=10, db_index=True)
    nta_name = models.CharField(max_length=100, blank=True, default="")
    delivery_method = models.CharField(
        max_length=10, choices=DELIVERY_CHOICES, default=DELIVERY_IN_APP
    )
    threshold = models.FloatField(
        default=0.5,
        help_text="Minimum score change to trigger alert",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "nta_code")
        verbose_name = "Area Subscription"
        verbose_name_plural = "Area Subscriptions"

    def __str__(self):
        return f"{self.user.username} → {self.nta_name or self.nta_code}"


class Notification(models.Model):
    """In-app notification for a user."""

    TYPE_RISK_CHANGE = "risk_change"
    TYPE_INGESTION = "ingestion"
    TYPE_CHOICES = [
        (TYPE_RISK_CHANGE, "Risk Score Change"),
        (TYPE_INGESTION, "Ingestion Complete"),
    ]

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    notification_type = models.CharField(
        max_length=20, choices=TYPE_CHOICES, default=TYPE_RISK_CHANGE
    )
    title = models.CharField(max_length=200)
    message = models.TextField()
    nta_code = models.CharField(max_length=10, blank=True, default="")
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"

    def __str__(self):
        return f"{self.user.username}: {self.title}"

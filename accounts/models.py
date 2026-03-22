from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Custom user with role-based access for TenantGuard NYC."""

    ROLE_PUBLIC = "public"
    ROLE_VERIFIED_TENANT = "verified_tenant"
    ROLE_ADMIN = "admin"

    ROLE_CHOICES = [
        (ROLE_PUBLIC, "Public User"),
        (ROLE_VERIFIED_TENANT, "Verified Tenant"),
        (ROLE_ADMIN, "Administrator"),
    ]

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_PUBLIC)
    phone_number = models.CharField(max_length=15, blank=True, default="")
    bio = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "user"
        verbose_name_plural = "users"

    def __str__(self):
        return self.username

    @property
    def is_verified_tenant(self):
        return self.role == self.ROLE_VERIFIED_TENANT

    @property
    def is_admin_user(self):
        return self.role == self.ROLE_ADMIN or self.is_superuser

    @property
    def display_role(self):
        return dict(self.ROLE_CHOICES).get(self.role, self.role)

    @property
    def has_pending_verification(self):
        """True when the user has a verification request awaiting review."""
        return self.verification_requests.filter(
            status=VerificationRequest.STATUS_PENDING
        ).exists()

    @property
    def verified_address(self):
        """Return the address from the most recent approved verification."""
        approved = (
            self.verification_requests.filter(
                status=VerificationRequest.STATUS_APPROVED
            )
            .order_by("-reviewed_at")
            .first()
        )
        return approved.address if approved else None

    @property
    def verified_nta_code(self):
        """Return the nta_code from the most recent approved verification."""
        approved = (
            self.verification_requests.filter(
                status=VerificationRequest.STATUS_APPROVED
            )
            .order_by("-reviewed_at")
            .first()
        )
        return approved.nta_code if approved else None


class VerificationRequest(models.Model):
    """
    A tenant submits a verification request tied to a specific building.
    An admin reviews the request and approves or rejects it.
    """

    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending Review"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
    ]

    DOCUMENT_TYPE_CHOICES = [
        ("lease", "Lease Agreement"),
        ("utility_bill", "Utility Bill"),
        ("bank_statement", "Bank Statement"),
        ("government_mail", "Government Mail"),
        ("other", "Other"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="verification_requests",
    )
    address = models.CharField(
        max_length=255,
        help_text="Full street address of the building (e.g. 123 Main St, Apt 4B, New York, NY 10001)",
    )
    borough = models.CharField(max_length=20, blank=True, default="")
    zip_code = models.CharField(max_length=10, blank=True, default="")
    nta_code = models.CharField(max_length=10, blank=True, default="", db_index=True)

    document_type = models.CharField(
        max_length=20,
        choices=DOCUMENT_TYPE_CHOICES,
        help_text="Type of proof-of-residency document",
    )
    document = models.FileField(
        upload_to="verification_documents/%Y/%m/",
        blank=True,
        null=True,
        help_text="Upload proof-of-residency document (PDF, JPG, or PNG — max 10 MB)",
    )
    document_description = models.TextField(
        blank=True,
        default="",
        help_text="Additional details about the document (e.g. date range, account holder name)",
    )

    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
    )
    admin_notes = models.TextField(
        blank=True,
        default="",
        help_text="Notes from the admin reviewer (visible to the user after review)",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_verifications",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Verification Request"
        verbose_name_plural = "Verification Requests"

    def __str__(self):
        return f"Verification #{self.pk} — {self.user.username} @ {self.address} [{self.get_status_display()}]"

    @property
    def is_pending(self):
        return self.status == self.STATUS_PENDING

    @property
    def is_approved(self):
        return self.status == self.STATUS_APPROVED

    @property
    def is_rejected(self):
        return self.status == self.STATUS_REJECTED

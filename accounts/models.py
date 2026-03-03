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

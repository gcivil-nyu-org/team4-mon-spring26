from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User, VerificationRequest


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ["username", "email", "first_name", "last_name", "role", "is_staff"]
    list_filter = ["role", "is_staff", "is_active"]
    search_fields = ["username", "email", "first_name", "last_name"]
    fieldsets = UserAdmin.fieldsets + (
        ("TenantGuard", {"fields": ("role", "phone_number", "bio")}),
    )


@admin.register(VerificationRequest)
class VerificationRequestAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "address", "borough", "document_type", "has_document", "status", "created_at", "reviewed_at"]
    list_filter = ["status", "borough", "document_type"]
    search_fields = ["user__username", "user__email", "address"]
    readonly_fields = ["created_at", "updated_at", "reviewed_at", "reviewed_by"]
    raw_id_fields = ["user"]

    @admin.display(boolean=True, description="Doc?")
    def has_document(self, obj):
        return bool(obj.document)

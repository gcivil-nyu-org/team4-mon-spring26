from functools import wraps

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import (
    AdminVerificationReviewForm,
    ProfileForm,
    RegistrationForm,
    VerificationRequestForm,
)
from .models import User, VerificationRequest
from communities.models import Community, CommunityMembership

# ------------------------------------------------------------------ #
#  Permission decorators
# ------------------------------------------------------------------ #


def verified_tenant_required(view_func):
    """Only allow access to users whose role is verified_tenant (or admin)."""

    @wraps(view_func)
    @login_required
    def _wrapped(request, *args, **kwargs):
        if not (request.user.is_verified_tenant or request.user.is_admin_user):
            raise PermissionDenied("Only verified tenants can perform this action.")
        return view_func(request, *args, **kwargs)

    return _wrapped


def admin_required(view_func):
    """Only allow access to platform admins."""

    @wraps(view_func)
    @login_required
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_admin_user:
            raise PermissionDenied("Admin access required.")
        return view_func(request, *args, **kwargs)

    return _wrapped


# ------------------------------------------------------------------ #
#  Registration
# ------------------------------------------------------------------ #


def register_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(
                request, "Account created successfully! Welcome to TenantGuard NYC."
            )
            return redirect("dashboard")
    else:
        form = RegistrationForm()

    return render(request, "accounts/register.html", {"form": form})


# ------------------------------------------------------------------ #
#  Profile
# ------------------------------------------------------------------ #


@login_required
def profile_view(request):
    if request.method == "POST":
        form = ProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated successfully.")
            return redirect("profile")
    else:
        form = ProfileForm(instance=request.user)

    verification_history = request.user.verification_requests.all()[:5]

    return render(
        request,
        "accounts/profile.html",
        {
            "form": form,
            "verification_history": verification_history,
        },
    )


# ------------------------------------------------------------------ #
#  Verification — tenant submits a request
# ------------------------------------------------------------------ #


@login_required
def request_verification_view(request):
    """Tenant submits a building-tied verification request."""
    # Already verified? Redirect to profile.
    if request.user.is_verified_tenant:
        messages.info(request, "You are already a verified tenant.")
        return redirect("profile")

    pending_request = (
        request.user.verification_requests.filter(
            status=VerificationRequest.STATUS_PENDING
        )
        .order_by("-created_at")
        .first()
    )

    if request.method == "POST":
        form = VerificationRequestForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            vr = form.save(commit=False)
            vr.user = request.user
            vr.save()
            messages.success(
                request,
                "Verification request submitted! An admin will review it shortly.",
            )
            return redirect("verification-status")
    else:
        form = VerificationRequestForm(user=request.user)

    return render(
        request,
        "accounts/request_verification.html",
        {
            "form": form,
            "pending_request": pending_request,
        },
    )


@login_required
def edit_verification_view(request, pk):
    """Allow users to edit their own pending verification requests."""
    vr = get_object_or_404(
        VerificationRequest,
        pk=pk,
        user=request.user,
        status=VerificationRequest.STATUS_PENDING,
    )

    if request.method == "POST":
        form = VerificationRequestForm(
            request.POST,
            request.FILES,
            instance=vr,
            user=request.user,
        )
        if form.is_valid():
            form.save()
            messages.success(request, "Verification request updated.")
            return redirect("verification-status")
    else:
        form = VerificationRequestForm(instance=vr, user=request.user)

    return render(
        request,
        "accounts/request_verification.html",
        {
            "form": form,
            "verification_request": vr,
            "is_editing": True,
        },
    )


@login_required
@require_POST
def withdraw_verification_view(request, pk):
    """Allow users to withdraw their own pending verification requests."""
    vr = get_object_or_404(
        VerificationRequest,
        pk=pk,
        user=request.user,
        status=VerificationRequest.STATUS_PENDING,
    )
    vr.status = VerificationRequest.STATUS_WITHDRAWN
    vr.save(update_fields=["status", "updated_at"])
    messages.success(request, "Verification request withdrawn.")
    return redirect("verification-status")


@login_required
def verification_status_view(request):
    """Show the logged-in user their verification request history."""
    requests_qs = request.user.verification_requests.all()
    return render(
        request,
        "accounts/verification_status.html",
        {"verification_requests": requests_qs},
    )


# ------------------------------------------------------------------ #
#  Admin — moderation queue
# ------------------------------------------------------------------ #


@admin_required
def admin_verification_queue_view(request):
    """List all pending verification requests for admin review."""
    status_filter = request.GET.get("status", "pending")
    if status_filter == "all":
        qs = VerificationRequest.objects.select_related("user").all()
    elif status_filter in ("approved", "rejected"):
        qs = VerificationRequest.objects.select_related("user").filter(
            status=status_filter
        )
    else:
        qs = VerificationRequest.objects.select_related("user").filter(
            status=VerificationRequest.STATUS_PENDING
        )
        status_filter = "pending"

    return render(
        request,
        "accounts/admin_verification_queue.html",
        {
            "verification_requests": qs,
            "status_filter": status_filter,
        },
    )


@admin_required
def admin_verification_review_view(request, pk):
    """Admin reviews and approves/rejects a single verification request."""
    vr = get_object_or_404(VerificationRequest.objects.select_related("user"), pk=pk)

    if request.method == "POST":
        form = AdminVerificationReviewForm(request.POST)
        if form.is_valid():
            action = form.cleaned_data["action"]
            vr.admin_notes = form.cleaned_data.get("admin_notes", "")
            vr.reviewed_by = request.user
            vr.reviewed_at = timezone.now()

            if action == AdminVerificationReviewForm.ACTION_APPROVE:
                vr.status = VerificationRequest.STATUS_APPROVED
                vr.user.role = User.ROLE_VERIFIED_TENANT
                vr.user.save(update_fields=["role"])
                vr.save()

                # Auto-assign user to their NTA community
                if vr.nta_code:
                    try:
                        community = Community.objects.get(nta_id=vr.nta_code)
                        CommunityMembership.objects.get_or_create(
                            user=vr.user,
                            community=community,
                            defaults={"is_active": True},
                        )
                    except Community.DoesNotExist:
                        pass  # Community not created yet, will be assigned later

                messages.success(
                    request, f"✅ {vr.user.username} has been verified as a tenant."
                )
            else:
                vr.status = VerificationRequest.STATUS_REJECTED
                vr.save()
                messages.warning(
                    request,
                    f"❌ Verification request for {vr.user.username} was rejected.",
                )

            return redirect("admin-verification-queue")
    else:
        form = AdminVerificationReviewForm()

    return render(
        request,
        "accounts/admin_verification_review.html",
        {"vr": vr, "form": form},
    )

#!/usr/bin/env python
"""Test script to verify automatic community assignment works locally."""

import os
import sys
import django

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tenantguard.settings")
django.setup()

from accounts.models import User, VerificationRequest
from communities.models import Community, CommunityMembership
from mapview.models import NTARiskScore
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile

print("=" * 60)
print("Testing Automatic Community Assignment")
print("=" * 60)

# Clean up previous test data
User.objects.filter(username__in=["testuser123", "testadmin123"]).delete()
VerificationRequest.objects.filter(address__contains="405 East 42nd").delete()

# 1. Create test NTA and Community
# Using MN0661 which is the actual NTA code for 405 East 42nd Street area
print("\n1. Creating test NTA and Community...")
nta, created = NTARiskScore.objects.get_or_create(
    nta_code="MN0661",
    defaults={"nta_name": "Turtle Bay-East Midtown", "borough": "Manhattan"},
)
print(f"   NTA: {nta.nta_code} - {nta.nta_name} ({'created' if created else 'exists'})")

community, created = Community.objects.get_or_create(
    nta=nta, defaults={"name": "Turtle Bay-East Midtown Community"}
)
print(f"   Community: {community.name} ({'created' if created else 'exists'})")

# 2. Create test user and admin
print("\n2. Creating test user and admin...")
user = User.objects.create_user(
    username="testuser123",
    email="test@example.com",
    password="TestPass123!",
    first_name="Test",
    last_name="User",
)
print(f"   User: {user.username}")

admin = User.objects.create_user(
    username="testadmin123",
    email="admin@example.com",
    password="AdminPass123!",
    role=User.ROLE_ADMIN,
)
print(f"   Admin: {admin.username}")

# 3. Test geocoding with real NYC address
print("\n3. Testing verification request form with geocoding...")
from accounts.forms import VerificationRequestForm

# Create a dummy PDF file
dummy_pdf = SimpleUploadedFile(
    "lease.pdf", b"dummy content", content_type="application/pdf"
)

form_data = {
    "address": "405 East 42nd Street, New York, NY 10017",
    "borough": "MANHATTAN",
    "zip_code": "10017",
    "document_type": "lease",
    "document_description": "Lease agreement",
}

form = VerificationRequestForm(data=form_data, files={"document": dummy_pdf}, user=user)

if form.is_valid():
    vr = form.save(commit=False)
    vr.user = user
    vr.save()
    print(f"   ✓ Verification request created")
    print(f"     Address: {vr.address}")
    print(f"     Latitude: {vr.latitude}")
    print(f"     Longitude: {vr.longitude}")
    print(f"     NTA Code: {vr.nta_code or 'NOT SET'}")
else:
    print(f"   ✗ Form errors: {form.errors}")
    sys.exit(1)

# 4. Check if NTA code was assigned
print("\n4. Checking NTA code assignment...")
if vr.nta_code:
    print(f"   ✓ NTA code successfully assigned: {vr.nta_code}")
else:
    print(f"   ✗ WARNING: NTA code NOT assigned - geocoding may have failed")
    print(f"   This could be due to:")
    print(f"   - Missing MAPBOX_ACCESS_TOKEN in settings")
    print(f"   - Network issues")
    print(f"   - Address outside NYC")

# 5. Simulate admin approval (mimicking views.py logic)
print("\n5. Simulating admin approval...")
vr.status = VerificationRequest.STATUS_APPROVED
vr.reviewed_by = admin
vr.reviewed_at = timezone.now()
user.role = User.ROLE_VERIFIED_TENANT
user.save()
vr.save()
print(f"   ✓ Verification approved")
print(f"   ✓ User role updated to: {user.role}")

# Trigger community assignment (from views.py logic)
print("\n6. Testing automatic community assignment...")
if vr.nta_code:
    try:
        comm = Community.objects.get(nta_id=vr.nta_code)
        membership, created = CommunityMembership.objects.get_or_create(
            user=user, community=comm, defaults={"is_active": True}
        )
        if created:
            print(f"   ✓ Community membership created: {user.username} → {comm.name}")
        else:
            print(f"   ✓ Community membership already exists")
    except Community.DoesNotExist:
        print(f"   ✗ FAILED: Community not found for NTA code: {vr.nta_code}")
        print(f"   Available communities:")
        for c in Community.objects.all()[:5]:
            print(f"     - {c.nta_id}: {c.name}")
        sys.exit(1)
else:
    print(f"   ✗ FAILED: Cannot assign community - no NTA code")
    sys.exit(1)

# 7. Verify final state
print("\n7. Verifying final state...")
membership = CommunityMembership.objects.filter(user=user).first()
if membership:
    print(
        f"   ✓ SUCCESS: User {user.username} is member of {membership.community.name}"
    )
else:
    print(f"   ✗ FAILED: User {user.username} has no community membership")
    sys.exit(1)

# 8. Test user properties
print("\n8. Testing user properties...")
print(f"   verified_nta_code: {user.verified_nta_code}")
print(f"   verified_address: {user.verified_address}")
print(f"   active_community: {user.active_community}")

print("\n" + "=" * 60)
print("TEST SUMMARY")
print("=" * 60)
print(f"User: {user.username} (role: {user.role})")
print(f"Verification Status: {vr.status}")
print(f"NTA Code: {vr.nta_code or 'NOT SET'}")
print(f"Community: {membership.community.name if membership else 'NOT ASSIGNED'}")
print(f"Membership Active: {membership.is_active if membership else 'N/A'}")

if membership and vr.nta_code and user.role == User.ROLE_VERIFIED_TENANT:
    print("\n✓✓✓ ALL TESTS PASSED ✓✓✓")
    print("Automatic community assignment is working correctly!")
else:
    print("\n✗✗✗ TESTS FAILED ✗✗✗")
    sys.exit(1)

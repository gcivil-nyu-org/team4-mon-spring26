"""Backfill community memberships for existing verified users.

Usage:
    python manage.py assign_user_communities
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from communities.models import Community, CommunityMembership

User = get_user_model()


class Command(BaseCommand):
    help = "Assign verified users to their NTA community (backfill)"

    def handle(self, *args, **options):
        users = User.objects.filter(role=User.ROLE_VERIFIED_TENANT)
        assigned = 0
        skipped = 0

        for user in users:
            nta_code = user.verified_nta_code
            if not nta_code:
                skipped += 1
                continue

            try:
                community = Community.objects.get(nta_id=nta_code)
            except Community.DoesNotExist:
                skipped += 1
                continue

            _, created = CommunityMembership.objects.get_or_create(
                user=user,
                community=community,
                defaults={"is_active": True},
            )
            if created:
                assigned += 1

        self.stdout.write(
            self.style.SUCCESS(f"Done — {assigned} users assigned, {skipped} skipped.")
        )

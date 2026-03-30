"""Create one Community per NTA neighbourhood (idempotent).

Usage:
    python manage.py create_nta_communities
"""

from django.core.management.base import BaseCommand

from communities.models import Community
from mapview.models import NTARiskScore


class Command(BaseCommand):
    help = "Create a Community for every NTA neighbourhood (idempotent)"

    def handle(self, *args, **options):
        ntas = NTARiskScore.objects.all()
        created = 0
        for nta in ntas:
            _, was_created = Community.objects.get_or_create(
                nta=nta,
                defaults={
                    "name": nta.nta_name,
                    "description": f"Community forum for {nta.nta_name}, {nta.borough}.",
                },
            )
            if was_created:
                created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Done — {created} communities created, "
                f"{ntas.count() - created} already existed."
            )
        )

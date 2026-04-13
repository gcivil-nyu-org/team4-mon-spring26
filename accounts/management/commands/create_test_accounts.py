"""Create test accounts for the Testing Party.

Usage:
    python manage.py create_test_accounts
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

User = get_user_model()

TEST_ACCOUNTS = [
    {
        "username": "prof_test",
        "email": "prof_test@tenantguard.nyc",
        "first_name": "Professor",
        "last_name": "Test",
        "password": "TenantGuard2026!",
    },
    {
        "username": "ta_test",
        "email": "ta_test@tenantguard.nyc",
        "first_name": "TA",
        "last_name": "Test",
        "password": "TenantGuard2026!",
    },
    {
        "username": "test1",
        "email": "test1@tenantguard.nyc",
        "first_name": "Test",
        "last_name": "User1",
        "password": "TenantGuard2026!",
    },
    {
        "username": "test2",
        "email": "test2@tenantguard.nyc",
        "first_name": "Test",
        "last_name": "User2",
        "password": "TenantGuard2026!",
    },
    {
        "username": "test3",
        "email": "test3@tenantguard.nyc",
        "first_name": "Test",
        "last_name": "User3",
        "password": "TenantGuard2026!",
    },
    {
        "username": "test4",
        "email": "test4@tenantguard.nyc",
        "first_name": "Test",
        "last_name": "User4",
        "password": "TenantGuard2026!",
    },
    {
        "username": "test5",
        "email": "test5@tenantguard.nyc",
        "first_name": "Test",
        "last_name": "User5",
        "password": "TenantGuard2026!",
    },
]


class Command(BaseCommand):
    help = "Create test accounts for the Testing Party"

    def handle(self, *args, **options):
        for acct in TEST_ACCOUNTS:
            user, created = User.objects.get_or_create(
                username=acct["username"],
                defaults={
                    "email": acct["email"],
                    "first_name": acct["first_name"],
                    "last_name": acct["last_name"],
                },
            )
            if created:
                user.set_password(acct["password"])
                user.save()
                self.stdout.write(
                    self.style.SUCCESS(f"Created account: {acct['username']}")
                )
            else:
                # Reset password in case it was changed
                user.set_password(acct["password"])
                user.save()
                self.stdout.write(
                    f"Account already exists (password reset): {acct['username']}"
                )

        self.stdout.write(self.style.SUCCESS("\nAll 7 test accounts are ready."))

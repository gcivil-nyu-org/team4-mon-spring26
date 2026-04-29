"""Create test accounts plus sample verified-community activity.

Usage:
    python manage.py create_test_accounts
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import VerificationRequest
from communities.models import Comment, Community, CommunityMembership, Post
from mapview.models import NTARiskScore

User = get_user_model()

DEFAULT_PASSWORD = "TenantGuard2026!"

PUBLIC_TEST_ACCOUNTS = [
    {
        "username": "prof_test",
        "email": "prof_test@tenantguard.nyc",
        "first_name": "Professor",
        "last_name": "Test",
    },
    {
        "username": "ta_test",
        "email": "ta_test@tenantguard.nyc",
        "first_name": "TA",
        "last_name": "Test",
    },
    {
        "username": "test1",
        "email": "test1@tenantguard.nyc",
        "first_name": "Test",
        "last_name": "User1",
    },
    {
        "username": "test2",
        "email": "test2@tenantguard.nyc",
        "first_name": "Test",
        "last_name": "User2",
    },
    {
        "username": "test3",
        "email": "test3@tenantguard.nyc",
        "first_name": "Test",
        "last_name": "User3",
    },
    {
        "username": "test4",
        "email": "test4@tenantguard.nyc",
        "first_name": "Test",
        "last_name": "User4",
    },
    {
        "username": "test5",
        "email": "test5@tenantguard.nyc",
        "first_name": "Test",
        "last_name": "User5",
    },
]

VERIFIED_TENANT_SEEDS = [
    {
        "username": "greenpoint_alex",
        "email": "greenpoint_alex@tenantguard.nyc",
        "first_name": "Alex",
        "last_name": "Rivera",
        "nta_code": "BK0101",
        "address": "145 Franklin St, Brooklyn, NY 11222",
        "zip_code": "11222",
        "posts": [
            {
                "title": "Boiler heat has been inconsistent this week",
                "content": (
                    "Has anyone else in Greenpoint noticed the heat cutting out "
                    "overnight? Our radiators have gone cold twice this week."
                ),
                "category": "maintenance",
            },
            {
                "title": "Good tenant lawyer recommendation?",
                "content": (
                    "Looking for a tenant-side attorney who has handled repair-delay "
                    "cases in North Brooklyn. Any firsthand recommendations?"
                ),
                "category": "resource",
            },
        ],
    },
    {
        "username": "fortgreene_maya",
        "email": "fortgreene_maya@tenantguard.nyc",
        "first_name": "Maya",
        "last_name": "Thompson",
        "nta_code": "BK0203",
        "address": "318 Lafayette Ave, Brooklyn, NY 11238",
        "zip_code": "11238",
        "posts": [
            {
                "title": "Anyone organizing around elevator outages?",
                "content": (
                    "Our building has had repeated elevator outages and management "
                    "keeps giving vague updates. Curious if any nearby tenants are "
                    "working on a joint complaint."
                ),
                "category": "organizing",
            }
        ],
    },
    {
        "username": "astoria_jordan",
        "email": "astoria_jordan@tenantguard.nyc",
        "first_name": "Jordan",
        "last_name": "Lee",
        "nta_code": "QN0101",
        "address": "24-18 31st St, Astoria, NY 11102",
        "zip_code": "11102",
        "posts": [
            {
                "title": "Noise issue from overnight construction",
                "content": (
                    "There has been overnight construction noise near Ditmars for "
                    "days now. Has anyone had success escalating this through 311?"
                ),
                "category": "noise",
            }
        ],
    },
    {
        "username": "fidi_sam",
        "email": "fidi_sam@tenantguard.nyc",
        "first_name": "Sam",
        "last_name": "Chen",
        "nta_code": "MN0101",
        "address": "10 Rector St, New York, NY 10006",
        "zip_code": "10006",
        "posts": [
            {
                "title": "Water shutdown notices have been too last-minute",
                "content": (
                    "Management keeps posting water shutdown notices with barely any lead time. "
                    "Has anyone found a good way to document this pattern for follow-up?"
                ),
                "category": "maintenance",
            },
            {
                "title": "Anyone tracking elevator outages near Battery Park City?",
                "content": (
                    "A few buildings nearby seem to be dealing with recurring elevator issues. "
                    "Trying to see whether tenants are noticing the same thing across FiDi."
                ),
                "category": "question",
            },
        ],
    },
]

POST_REPLIES = {
    "Boiler heat has been inconsistent this week": [
        (
            "fortgreene_maya",
            "We had something similar last winter. Document the dates and temperatures before reaching out.",
        ),
        (
            "astoria_jordan",
            "If the outage is overnight, include that pattern in the complaint because it gets overlooked.",
        ),
    ],
    "Good tenant lawyer recommendation?": [
        (
            "fortgreene_maya",
            "I can message you the clinic we used. They were especially helpful with repairs and access issues.",
        )
    ],
    "Anyone organizing around elevator outages?": [
        (
            "greenpoint_alex",
            "A shared log from residents helped our building show it was a recurring safety issue, not a one-off.",
        ),
        (
            "astoria_jordan",
            "A tenant association meeting might be worth it if management keeps stalling.",
        ),
    ],
    "Noise issue from overnight construction": [
        (
            "greenpoint_alex",
            "We had better luck after including exact hours and the contractor name in the report.",
        )
    ],
    "Water shutdown notices have been too last-minute": [
        (
            "fortgreene_maya",
            "Save photos of each notice with timestamps. That helped us show the pattern clearly.",
        ),
        (
            "fidi_sam",
            "I am also keeping a simple log with the outage date, notice time, and when service came back.",
        ),
    ],
    "Anyone tracking elevator outages near Battery Park City?": [
        (
            "greenpoint_alex",
            "If multiple buildings are seeing it, a shared spreadsheet of outage times might be useful.",
        ),
        (
            "astoria_jordan",
            "Repeated outages plus accessibility impact usually gets more attention when residents report together.",
        ),
    ],
}


class Command(BaseCommand):
    help = "Create test accounts plus verified users, posts, and comments"

    def handle(self, *args, **options):
        public_count = self._create_public_accounts()
        verified_users = self._create_verified_users()
        post_count, comment_count = self._seed_community_activity(verified_users)

        self.stdout.write(
            self.style.SUCCESS(
                "\nSeed complete: "
                f"{public_count} public test accounts, "
                f"{len(verified_users)} verified tenants, "
                f"{post_count} posts, {comment_count} comments."
            )
        )

    def _create_public_accounts(self):
        created_or_reset = 0
        for acct in PUBLIC_TEST_ACCOUNTS:
            user, created = User.objects.get_or_create(
                username=acct["username"],
                defaults={
                    "email": acct["email"],
                    "first_name": acct["first_name"],
                    "last_name": acct["last_name"],
                },
            )
            if not created:
                user.email = acct["email"]
                user.first_name = acct["first_name"]
                user.last_name = acct["last_name"]
            user.set_password(DEFAULT_PASSWORD)
            user.save()
            created_or_reset += 1
            action = "Created" if created else "Updated"
            self.stdout.write(f"{action} public account: {acct['username']}")
        return created_or_reset

    def _create_verified_users(self):
        verified_users = {}

        for seed in VERIFIED_TENANT_SEEDS:
            nta = NTARiskScore.objects.filter(nta_code=seed["nta_code"]).first()
            if not nta:
                self.stdout.write(
                    self.style.WARNING(
                        f"Skipping {seed['username']} — NTA {seed['nta_code']} not found."
                    )
                )
                continue

            user, created = User.objects.get_or_create(
                username=seed["username"],
                defaults={
                    "email": seed["email"],
                    "first_name": seed["first_name"],
                    "last_name": seed["last_name"],
                    "role": User.ROLE_VERIFIED_TENANT,
                },
            )
            user.email = seed["email"]
            user.first_name = seed["first_name"]
            user.last_name = seed["last_name"]
            user.role = User.ROLE_VERIFIED_TENANT
            user.set_password(DEFAULT_PASSWORD)
            user.save()

            community, _ = Community.objects.get_or_create(
                nta=nta,
                defaults={
                    "name": nta.nta_name,
                    "description": f"Community forum for {nta.nta_name}, {nta.borough}.",
                },
            )
            membership, membership_created = CommunityMembership.objects.get_or_create(
                user=user,
                community=community,
                defaults={"is_active": True},
            )
            if not membership.is_active:
                membership.is_active = True
                membership.save(update_fields=["is_active"])

            VerificationRequest.objects.update_or_create(
                user=user,
                nta_code=seed["nta_code"],
                address=seed["address"],
                defaults={
                    "borough": nta.borough.upper(),
                    "zip_code": seed["zip_code"],
                    "document_type": "lease",
                    "document_description": "Seeded verified tenant account for demos.",
                    "status": VerificationRequest.STATUS_APPROVED,
                    "reviewed_at": timezone.now(),
                    "admin_notes": "Auto-approved demo seed account.",
                },
            )

            verified_users[user.username] = {"user": user, "nta": nta, "seed": seed}
            action = "Created" if created else "Updated"
            membership_note = " and community membership" if membership_created else ""
            self.stdout.write(
                f"{action} verified tenant: {user.username} ({nta.nta_name}){membership_note}"
            )

        return verified_users

    def _seed_community_activity(self, verified_users):
        created_posts = 0
        created_comments = 0
        posts_by_title = {}

        for payload in verified_users.values():
            user = payload["user"]
            nta = payload["nta"]
            for post_seed in payload["seed"]["posts"]:
                post, created = Post.objects.get_or_create(
                    nta=nta,
                    author=user,
                    title=post_seed["title"],
                    defaults={
                        "content": post_seed["content"],
                        "category": post_seed["category"],
                    },
                )
                if not created:
                    post.content = post_seed["content"]
                    post.category = post_seed["category"]
                    post.is_active = True
                    post.save(
                        update_fields=["content", "category", "is_active", "updated_at"]
                    )
                created_posts += 1 if created else 0
                posts_by_title[post.title] = post

        for post_title, replies in POST_REPLIES.items():
            post = posts_by_title.get(post_title)
            if not post:
                continue
            for author_username, content in replies:
                author_payload = verified_users.get(author_username)
                if not author_payload:
                    continue
                _, created = Comment.objects.get_or_create(
                    post=post,
                    author=author_payload["user"],
                    content=content,
                )
                created_comments += 1 if created else 0

        return len(posts_by_title), created_comments

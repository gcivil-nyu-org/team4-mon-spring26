"""Health check endpoint for AWS Elastic Beanstalk and monitoring."""

from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.views.decorators.cache import never_cache


@require_GET
@never_cache
def health_check_view(request):
    """
    Simple health check endpoint that returns 200 OK.

    This endpoint is used by AWS Elastic Beanstalk health checks
    and doesn't require database access to avoid false negatives
    during high load or database maintenance.
    """
    return JsonResponse({"status": "healthy"}, status=200)

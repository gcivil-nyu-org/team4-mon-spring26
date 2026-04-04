"""Views for public landlord portfolio (Epic #9).

Aggregates HPD violations and 311 complaints by BBL (building) to provide
a consolidated view of properties. Users can search by address or BBL to
find all violations associated with buildings at that location.
"""

from django.db.models import Count, Max, Q
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from .models import Complaint311, HPDViolation


@require_GET
def landlord_search_view(request):
    """Search buildings by address to find landlord/building portfolio.

    Query params:
        q: search query (address fragment, street name, etc.)
        borough: optional borough filter
    """
    query = request.GET.get("q", "").strip()
    if len(query) < 3:
        return JsonResponse(
            {"error": "Query must be at least 3 characters."}, status=400
        )

    borough = request.GET.get("borough", "").strip().upper()

    # Find distinct buildings (by BBL) matching the query
    qs = HPDViolation.objects.exclude(bbl="").filter(
        Q(street_name__icontains=query)
        | Q(house_number__icontains=query)
        | Q(bbl__icontains=query)
    )
    if borough:
        qs = qs.filter(borough__icontains=borough)

    buildings = (
        qs.values("bbl", "house_number", "street_name", "borough", "zip_code")
        .annotate(
            violation_count=Count("id"),
            latest_inspection=Max("inspection_date"),
        )
        .order_by("-violation_count")[:20]
    )

    results = [
        {
            "bbl": b["bbl"],
            "address": f"{b['house_number']} {b['street_name']}".strip(),
            "borough": b["borough"],
            "zip_code": b["zip_code"],
            "violation_count": b["violation_count"],
            "latest_inspection": (
                b["latest_inspection"].isoformat() if b["latest_inspection"] else None
            ),
        }
        for b in buildings
    ]

    return JsonResponse({"count": len(results), "buildings": results})


@require_GET
def building_portfolio_view(request):
    """Get detailed violation/complaint portfolio for a specific building (BBL).

    Query params:
        bbl: Borough-Block-Lot identifier
    """
    bbl = request.GET.get("bbl", "").strip()
    if not bbl:
        return JsonResponse({"error": "bbl parameter is required."}, status=400)

    # Get violations for this building
    violations = HPDViolation.objects.filter(bbl=bbl).order_by("-inspection_date")
    complaints = Complaint311.objects.filter(bbl=bbl).order_by("-created_date")

    # Build address from first violation
    first_v = violations.first()
    address = first_v.address if first_v else ""
    borough = first_v.borough if first_v else ""
    zip_code = first_v.zip_code if first_v else ""

    # Aggregate stats
    total_violations = violations.count()
    total_complaints = complaints.count()
    class_a = violations.filter(violation_class="A").count()
    class_b = violations.filter(violation_class="B").count()
    class_c = violations.filter(violation_class="C").count()
    open_violations = violations.filter(
        Q(current_status__icontains="open") | Q(violation_status__icontains="open")
    ).count()

    # Top complaint types
    top_types = (
        complaints.values("complaint_type").annotate(n=Count("id")).order_by("-n")[:5]
    )

    # Recent violations (last 10)
    recent_violations = [
        {
            "violation_id": v.violation_id,
            "address": v.address,
            "apartment": v.apartment,
            "violation_class": v.violation_class,
            "inspection_date": (
                v.inspection_date.isoformat() if v.inspection_date else None
            ),
            "nov_description": v.nov_description,
            "current_status": v.current_status,
            "violation_status": v.violation_status,
        }
        for v in violations[:10]
    ]

    # Recent complaints (last 10)
    recent_complaints = [
        {
            "unique_key": c.unique_key,
            "created_date": (c.created_date.isoformat() if c.created_date else None),
            "complaint_type": c.complaint_type,
            "descriptor": c.descriptor,
            "status": c.status,
        }
        for c in complaints[:10]
    ]

    return JsonResponse(
        {
            "bbl": bbl,
            "address": address,
            "borough": borough,
            "zip_code": zip_code,
            "summary": {
                "total_violations": total_violations,
                "total_complaints": total_complaints,
                "class_a_violations": class_a,
                "class_b_violations": class_b,
                "class_c_violations": class_c,
                "open_violations": open_violations,
                "top_complaint_types": [
                    {"type": t["complaint_type"], "count": t["n"]} for t in top_types
                ],
            },
            "recent_violations": recent_violations,
            "recent_complaints": recent_complaints,
        }
    )


@require_GET
def landlord_portfolio_view(request):
    """Get portfolio of all buildings sharing similar ownership patterns.

    Uses BBL prefix (borough + block) to find related buildings,
    which often share the same landlord/owner.

    Query params:
        bbl: BBL of a known building (uses borough+block prefix to find related)
    """
    bbl = request.GET.get("bbl", "").strip()
    if not bbl or len(bbl) < 6:
        return JsonResponse(
            {"error": "A valid bbl parameter is required (min 6 chars)."},
            status=400,
        )

    # Use borough + block prefix (first ~6 digits) to find related buildings
    # BBL format: borough(1) + block(5) + lot(4)
    block_prefix = bbl[:6]

    related_bbls = (
        HPDViolation.objects.filter(bbl__startswith=block_prefix)
        .exclude(bbl="")
        .values("bbl")
        .annotate(
            violation_count=Count("id"),
            latest_inspection=Max("inspection_date"),
        )
        .order_by("-violation_count")
    )

    buildings = []
    total_violations_all = 0
    total_complaints_all = 0

    for entry in related_bbls:
        b_bbl = entry["bbl"]
        first_v = HPDViolation.objects.filter(bbl=b_bbl).first()
        c_count = Complaint311.objects.filter(bbl=b_bbl).count()
        total_violations_all += entry["violation_count"]
        total_complaints_all += c_count

        buildings.append(
            {
                "bbl": b_bbl,
                "address": first_v.address if first_v else "",
                "borough": first_v.borough if first_v else "",
                "zip_code": first_v.zip_code if first_v else "",
                "violation_count": entry["violation_count"],
                "complaint_count": c_count,
                "latest_inspection": (
                    entry["latest_inspection"].isoformat()
                    if entry["latest_inspection"]
                    else None
                ),
            }
        )

    return JsonResponse(
        {
            "block_prefix": block_prefix,
            "building_count": len(buildings),
            "total_violations": total_violations_all,
            "total_complaints": total_complaints_all,
            "buildings": buildings,
        }
    )

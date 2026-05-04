import os
import re

from django import forms
from django.conf import settings
from django.contrib.auth.forms import UserCreationForm
import requests
from urllib.parse import quote

from .models import User, VerificationRequest
from mapview.utils import get_nta_code_from_coordinates
from mapview.models import NTARiskScore

ALLOWED_DOCUMENT_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}
MAX_DOCUMENT_SIZE_MB = 10


def _extract_mapbox_context(feature):
    """Extract borough and ZIP code from a Mapbox feature when available."""
    zip_code = ""

    for item in feature.get("context", []):
        item_id = item.get("id", "")
        text = (item.get("text") or "").strip()
        if item_id.startswith("postcode.") and text:
            zip_code = text

    if not zip_code:
        match = re.search(r"\b(\d{5})\b", feature.get("place_name", ""))
        if match:
            zip_code = match.group(1)

    return zip_code


def resolve_verification_address(address):
    """Resolve an address to a canonical label, coordinates, borough, ZIP, and NTA code."""
    if not address or not settings.MAPBOX_ACCESS_TOKEN:
        return None

    encoded_query = quote(address.strip(), safe="")
    url = f"https://api.mapbox.com/geocoding/v5/mapbox.places/{encoded_query}.json"
    params = {
        "access_token": settings.MAPBOX_ACCESS_TOKEN,
        "limit": 1,
        "autocomplete": "true",
        "types": "address,place",
        "bbox": "-74.25559,40.49612,-73.70001,40.91553",
    }

    response = requests.get(url, params=params, timeout=8)
    response.raise_for_status()
    data = response.json()

    features = data.get("features", [])
    if not features:
        return None

    top = features[0]
    center = top.get("center", [])
    if len(center) != 2:
        return None

    lng, lat = center
    nta_code = get_nta_code_from_coordinates(lat, lng)
    if not nta_code:
        return None

    zip_code = _extract_mapbox_context(top)
    borough = (
        NTARiskScore.objects.filter(nta_code=nta_code)
        .values_list("borough", flat=True)
        .first()
        or ""
    ).upper()

    return {
        "label": top.get("place_name", address),
        "latitude": lat,
        "longitude": lng,
        "nta_code": nta_code,
        "borough": borough,
        "zip_code": zip_code,
    }


class RegistrationForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        error_messages={"required": "Email is required."},
        widget=forms.EmailInput(attrs={"placeholder": "Email"}),
    )
    first_name = forms.CharField(
        max_length=30,
        required=True,
        error_messages={"required": "First name is required."},
        widget=forms.TextInput(attrs={"placeholder": "First name"}),
    )
    last_name = forms.CharField(
        max_length=30,
        required=True,
        error_messages={"required": "Last name is required."},
        widget=forms.TextInput(attrs={"placeholder": "Last name"}),
    )

    class Meta:
        model = User
        fields = [
            "username",
            "email",
            "first_name",
            "last_name",
            "password1",
            "password2",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs["placeholder"] = "Username"
        self.fields["username"].error_messages["required"] = "Username is required."
        self.fields["password1"].widget.attrs["placeholder"] = "Password"
        self.fields["password1"].error_messages["required"] = "Password is required."
        self.fields["password2"].widget.attrs["placeholder"] = "Confirm password"
        self.fields["password2"].error_messages[
            "required"
        ] = "Password confirmation is required."


class ProfileForm(forms.ModelForm):
    first_name = forms.CharField(
        max_length=30,
        required=True,
        error_messages={"required": "First name is required."},
        widget=forms.TextInput(attrs={"placeholder": "First name"}),
    )
    last_name = forms.CharField(
        max_length=30,
        required=True,
        error_messages={"required": "Last name is required."},
        widget=forms.TextInput(attrs={"placeholder": "Last name"}),
    )
    email = forms.EmailField(
        required=True,
        error_messages={"required": "Email is required."},
        widget=forms.EmailInput(attrs={"placeholder": "Email"}),
    )

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "phone_number", "bio"]
        widgets = {
            "bio": forms.Textarea(
                attrs={"rows": 3, "placeholder": "Tell us about yourself..."}
            ),
            "phone_number": forms.TextInput(
                attrs={
                    "placeholder": "2015551234",
                    "inputmode": "numeric",
                    "pattern": "[0-9]*",
                }
            ),
        }

    def clean_phone_number(self):
        phone_number = (self.cleaned_data.get("phone_number") or "").strip()
        if not phone_number:
            return phone_number
        if not phone_number.isdigit() or len(phone_number) != 10:
            raise forms.ValidationError("Phone number must contain exactly 10 digits.")
        return phone_number


class VerificationRequestForm(forms.ModelForm):
    """Form for tenants to request building-level verification."""

    verified_address = forms.CharField(required=False, widget=forms.HiddenInput())
    verified_latitude = forms.FloatField(required=False, widget=forms.HiddenInput())
    verified_longitude = forms.FloatField(required=False, widget=forms.HiddenInput())
    verified_nta_code = forms.CharField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = VerificationRequest
        fields = [
            "address",
            "document_type",
            "document",
            "document_description",
            "verified_address",
            "verified_latitude",
            "verified_longitude",
            "verified_nta_code",
        ]
        widgets = {
            "address": forms.TextInput(
                attrs={
                    "placeholder": "e.g. 123 Main St, Apt 4B, New York, NY 10001",
                }
            ),
            "document_type": forms.Select(),
            "document": forms.ClearableFileInput(
                attrs={
                    "accept": ".pdf,.jpg,.jpeg,.png",
                }
            ),
            "document_description": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Describe your proof document — e.g. 'Con Edison bill dated Feb 2026 in my name'",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        self._resolved_address = None
        if self.instance.pk and self.instance.latitude and self.instance.longitude:
            self.fields["verified_address"].initial = self.instance.address
            self.fields["verified_latitude"].initial = self.instance.latitude
            self.fields["verified_longitude"].initial = self.instance.longitude
            self.fields["verified_nta_code"].initial = self.instance.nta_code

    def clean_document(self):
        document = self.cleaned_data.get("document")
        if document:
            ext = os.path.splitext(document.name)[1].lower()
            if ext not in ALLOWED_DOCUMENT_EXTENSIONS:
                raise forms.ValidationError(
                    f"Unsupported file type '{ext}'. Allowed: PDF, JPG, PNG."
                )
            max_bytes = MAX_DOCUMENT_SIZE_MB * 1024 * 1024
            if document.size > max_bytes:
                raise forms.ValidationError(
                    f"File too large ({document.size / (1024*1024):.1f} MB). "
                    f"Maximum allowed size is {MAX_DOCUMENT_SIZE_MB} MB."
                )
        return document

    def clean(self):
        cleaned = super().clean()

        if self.user:
            pending_requests = self.user.verification_requests.filter(
                status=VerificationRequest.STATUS_PENDING
            )
            if self.instance.pk:
                pending_requests = pending_requests.exclude(pk=self.instance.pk)
            if pending_requests.exists():
                raise forms.ValidationError(
                    "You already have a verification request pending review. "
                    "Please wait for it to be processed before submitting a new one."
                )

        address = (cleaned.get("address") or "").strip()
        verified_address = (cleaned.get("verified_address") or "").strip()
        verified_latitude = cleaned.get("verified_latitude")
        verified_longitude = cleaned.get("verified_longitude")
        verified_nta_code = (cleaned.get("verified_nta_code") or "").strip()

        if address:
            try:
                resolved = resolve_verification_address(address)
            except requests.RequestException:
                raise forms.ValidationError(
                    "We couldn't verify that address right now. Please try again in a moment."
                )
            except ValueError:
                raise forms.ValidationError(
                    "The address verification service returned invalid data. Please try again."
                )

            if not resolved:
                raise forms.ValidationError(
                    "Enter a valid NYC address within a mapped NTA before submitting."
                )

            if not (
                verified_address
                and verified_latitude is not None
                and verified_longitude is not None
                and verified_nta_code
            ):
                raise forms.ValidationError(
                    "Please verify and select your address from the suggested match before submitting."
                )

            if (
                verified_address != resolved["label"]
                or float(verified_latitude) != resolved["latitude"]
                or float(verified_longitude) != resolved["longitude"]
                or verified_nta_code != resolved["nta_code"]
            ):
                raise forms.ValidationError(
                    "Your address changed or no longer matches the verified selection. Please verify it again."
                )

            self._resolved_address = resolved

        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)

        if self._resolved_address:
            instance.address = self._resolved_address["label"]
            instance.latitude = self._resolved_address["latitude"]
            instance.longitude = self._resolved_address["longitude"]
            instance.nta_code = self._resolved_address["nta_code"]
            instance.borough = self._resolved_address["borough"]
            instance.zip_code = self._resolved_address["zip_code"]

        if commit:
            instance.save()
        return instance


class AdminVerificationReviewForm(forms.Form):
    """Form for admins to approve / reject a verification request."""

    ACTION_APPROVE = "approve"
    ACTION_REJECT = "reject"

    ACTION_CHOICES = [
        (ACTION_APPROVE, "Approve"),
        (ACTION_REJECT, "Reject"),
    ]

    action = forms.ChoiceField(choices=ACTION_CHOICES, widget=forms.HiddenInput())
    admin_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "placeholder": "Notes to the applicant (optional)…",
            }
        ),
    )

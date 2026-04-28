import os

from django import forms
from django.conf import settings
from django.contrib.auth.forms import UserCreationForm
import requests
from urllib.parse import quote

from .models import User, VerificationRequest
from mapview.utils import get_nta_code_from_coordinates

ALLOWED_DOCUMENT_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}
MAX_DOCUMENT_SIZE_MB = 10


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
        self.fields["password1"].error_messages["required"] = (
            "Password is required."
        )
        self.fields["password2"].widget.attrs["placeholder"] = "Confirm password"
        self.fields["password2"].error_messages["required"] = (
            "Password confirmation is required."
        )


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
            "phone_number": forms.TextInput(attrs={"placeholder": "Phone number"}),
        }


class VerificationRequestForm(forms.ModelForm):
    """Form for tenants to request building-level verification."""

    class Meta:
        model = VerificationRequest
        fields = [
            "address",
            "borough",
            "zip_code",
            "document_type",
            "document",
            "document_description",
        ]
        widgets = {
            "address": forms.TextInput(
                attrs={
                    "placeholder": "e.g. 123 Main St, Apt 4B, New York, NY 10001",
                }
            ),
            "borough": forms.Select(
                choices=[
                    ("", "Select borough"),
                    ("MANHATTAN", "Manhattan"),
                    ("BROOKLYN", "Brooklyn"),
                    ("QUEENS", "Queens"),
                    ("BRONX", "Bronx"),
                    ("STATEN ISLAND", "Staten Island"),
                ],
            ),
            "zip_code": forms.TextInput(attrs={"placeholder": "10001"}),
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
        if self.user and self.user.has_pending_verification:
            raise forms.ValidationError(
                "You already have a verification request pending review. "
                "Please wait for it to be processed before submitting a new one."
            )
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)

        # Geocode the address to get coordinates and NTA code
        address = instance.address
        if address and settings.MAPBOX_ACCESS_TOKEN:
            try:
                # Call Mapbox geocoding API
                encoded_query = quote(address, safe="")
                url = f"https://api.mapbox.com/geocoding/v5/mapbox.places/{encoded_query}.json"
                params = {
                    "access_token": settings.MAPBOX_ACCESS_TOKEN,
                    "limit": 1,
                    "types": "address,place",
                    "bbox": "-74.25559,40.49612,-73.70001,40.91553",  # NYC bounds
                }
                response = requests.get(url, params=params, timeout=8)
                response.raise_for_status()
                data = response.json()

                features = data.get("features", [])
                if features:
                    center = features[0].get("center", [])
                    if len(center) == 2:
                        instance.longitude = center[0]
                        instance.latitude = center[1]

                        # Get NTA code from coordinates
                        nta_code = get_nta_code_from_coordinates(
                            instance.latitude, instance.longitude
                        )
                        if nta_code:
                            instance.nta_code = nta_code
            except Exception:
                # Geocoding failed, but don't block submission
                # Admin can manually set NTA code during review
                pass

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

import os

from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import User, VerificationRequest

ALLOWED_DOCUMENT_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}
MAX_DOCUMENT_SIZE_MB = 10


class RegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={"placeholder": "Email"}))
    first_name = forms.CharField(max_length=30, required=True, widget=forms.TextInput(attrs={"placeholder": "First name"}))
    last_name = forms.CharField(max_length=30, required=True, widget=forms.TextInput(attrs={"placeholder": "Last name"}))

    class Meta:
        model = User
        fields = ["username", "email", "first_name", "last_name", "password1", "password2"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs["placeholder"] = "Username"
        self.fields["password1"].widget.attrs["placeholder"] = "Password"
        self.fields["password2"].widget.attrs["placeholder"] = "Confirm password"


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "phone_number", "bio"]
        widgets = {
            "bio": forms.Textarea(attrs={"rows": 3, "placeholder": "Tell us about yourself..."}),
            "phone_number": forms.TextInput(attrs={"placeholder": "Phone number"}),
        }


class VerificationRequestForm(forms.ModelForm):
    """Form for tenants to request building-level verification."""

    class Meta:
        model = VerificationRequest
        fields = ["address", "borough", "zip_code", "document_type", "document", "document_description"]
        widgets = {
            "address": forms.TextInput(attrs={
                "placeholder": "e.g. 123 Main St, Apt 4B, New York, NY 10001",
            }),
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
            "document": forms.ClearableFileInput(attrs={
                "accept": ".pdf,.jpg,.jpeg,.png",
            }),
            "document_description": forms.Textarea(attrs={
                "rows": 3,
                "placeholder": "Describe your proof document — e.g. 'Con Edison bill dated Feb 2026 in my name'",
            }),
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
        widget=forms.Textarea(attrs={
            "rows": 3,
            "placeholder": "Notes to the applicant (optional)…",
        }),
    )

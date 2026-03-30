from django import forms
from .models import Post, Comment, Report, DirectMessage


class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ["title", "content", "category", "linked_address", "image"]
        widgets = {
            "title": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Enter a clear title..."}
            ),
            "content": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": "What do you want to start a discussion about?",
                }
            ),
            "category": forms.Select(attrs={"class": "form-control"}),
            "linked_address": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Optional: link a building address",
                }
            ),
        }

    def clean_image(self):
        image = self.cleaned_data.get("image")
        if image and hasattr(image, "size"):
            if image.size > 5 * 1024 * 1024:
                raise forms.ValidationError("Image must be under 5 MB.")
        return image


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ["content"]
        widgets = {
            "content": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Write your reply...",
                }
            ),
        }


class ReportForm(forms.ModelForm):
    class Meta:
        model = Report
        fields = ["reason"]
        widgets = {
            "reason": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Please provide the reason for reporting this content.",
                }
            ),
        }


class DirectMessageForm(forms.ModelForm):
    class Meta:
        model = DirectMessage
        fields = ["content"]
        widgets = {
            "content": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Type your message...",
                }
            ),
        }

from django import forms
from .models import Post, Comment, Report


class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ["title", "content"]
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
        }


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

from django.core.exceptions import ValidationError


class StrongPasswordValidator:
    """Require mixed-character passwords for user accounts."""

    def validate(self, password, user=None):
        has_upper = any(char.isupper() for char in password)
        has_lower = any(char.islower() for char in password)
        has_digit = any(char.isdigit() for char in password)
        has_symbol = any(not char.isalnum() for char in password)

        if not (has_upper and has_lower and has_digit and has_symbol):
            raise ValidationError(
                "Password must include uppercase, lowercase, number, and symbol characters.",
                code="password_too_weak",
            )

    def get_help_text(self):
        return (
            "Your password must include uppercase, lowercase, number, and symbol "
            "characters."
        )

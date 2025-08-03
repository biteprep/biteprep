# users/forms.py (Complete, updated file)

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils.html import format_html
from django.urls import reverse_lazy

class CustomUserCreationForm(UserCreationForm):
    # We explicitly define the fields to override their default help_text and widgets.
    username = forms.CharField(
        max_length=150,
        help_text=None,  # Remove the default help text
        widget=forms.TextInput(attrs={'placeholder': 'Username', 'autocomplete': 'username'}),
        error_messages={'required': 'Please enter a username.'}
    )
    
    email = forms.EmailField(
        required=True,
        help_text=None, # Remove the default help text
        widget=forms.EmailInput(attrs={'placeholder': 'Email Address', 'autocomplete': 'email'}),
        error_messages={
            'required': 'Please enter your email address.',
            'invalid': 'Please enter a valid email address.'
        }
    )

    password1 = forms.CharField(
        label='Password',
        strip=False,
        widget=forms.PasswordInput(attrs={'placeholder': 'Password', 'autocomplete': 'new-password'}),
        help_text=None, # Remove all the default password validation help text
        error_messages={'required': 'Please enter a password.'}
    )

    password2 = forms.CharField(
        label='Password confirmation',
        strip=False,
        widget=forms.PasswordInput(attrs={'placeholder': 'Confirm Password', 'autocomplete': 'new-password'}),
        help_text=None, # Remove the "Enter the same password" help text
        error_messages={'required': 'Please confirm your password.'}
    )

    terms_agreement = forms.BooleanField(
        required=True,
        label=format_html(
            'I have read and agree to the <a href="{}" target="_blank">Terms and Conditions</a> and <a href="{}" target="_blank">Privacy Policy</a>.',
            reverse_lazy('terms_page'),
            reverse_lazy('privacy_page')
        ),
        error_messages={'required': 'You must agree to the terms and conditions to create an account.'}
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email") # The order of fields on the form

    def clean_email(self):
        """
        Verify that the email address is not already in use.
        """
        email = self.cleaned_data.get('email').lower()
        if User.objects.filter(email__iexact=email).exists():
            # This error message will appear if the email is already taken.
            raise ValidationError("This email address is already in use. Please use a different one.")
        return email
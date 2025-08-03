# users/forms.py

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils.html import format_html
# Use standard 'reverse' instead of 'reverse_lazy' inside methods
from django.urls import reverse

class CustomUserCreationForm(UserCreationForm):
    # We explicitly define the fields to override their default help_text and widgets.
    username = forms.CharField(
        max_length=150,
        help_text=None,
        widget=forms.TextInput(attrs={'placeholder': 'Username', 'autocomplete': 'username'}),
        error_messages={'required': 'Please enter a username.'}
    )
    
    email = forms.EmailField(
        required=True,
        help_text=None,
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
        help_text=None,
        error_messages={'required': 'Please enter a password.'}
    )

    password2 = forms.CharField(
        label='Password confirmation',
        strip=False,
        widget=forms.PasswordInput(attrs={'placeholder': 'Confirm Password', 'autocomplete': 'new-password'}),
        help_text=None,
        error_messages={'required': 'Please confirm your password.'}
    )

    # Define the field with a simple placeholder label. We will update it dynamically.
    terms_agreement = forms.BooleanField(
        required=True,
        label='I agree to the site policies.',
        error_messages={'required': 'You must agree to the terms and conditions to create an account.'}
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")

    def __init__(self, *args, **kwargs):
        """
        Override the init method to dynamically create the label with URLs.
        """
        super().__init__(*args, **kwargs) # Call the parent's __init__ method first
        
        # Get the URLs for the legal pages
        terms_url = reverse('terms_page')
        privacy_url = reverse('privacy_page')
        
        # Update the 'terms_agreement' field's label with the formatted HTML
        self.fields['terms_agreement'].label = format_html(
            'I have read and agree to the <a href="{}" target="_blank">Terms and Conditions</a> and <a href="{}" target="_blank">Privacy Policy</a>.',
            terms_url,
            privacy_url
        )

    def clean_email(self):
        """
        Verify that the email address is not already in use.
        """
        email = self.cleaned_data.get('email').lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("This email address is already in use. Please use a different one.")
        return email
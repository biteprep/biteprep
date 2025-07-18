# users/views.py

from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
import stripe

# This now imports the corrected form
from .forms import CustomUserCreationForm

def signup(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('signup_success')
    else:
        form = CustomUserCreationForm()
    
    # This line has been corrected to point to the 'registration' folder.
    return render(request, 'registration/signup.html', {'form': form})

@login_required
def signup_success(request):
    """
    Displays a success page after signup before redirecting.
    """
    return render(request, 'registration/signup_success.html')

def logout_view(request):
    logout(request)
    messages.info(request, "You have been successfully logged out.")
    return redirect('home')

@login_required
def account_page(request):
    return render(request, 'registration/account_page.html')

@login_required
def delete_account(request):
    if request.method == 'POST':
        user = request.user
        logout(request)
        user.delete()
        messages.success(request, "Your account has been successfully deleted.")
        return redirect('home')
    return redirect('account')

@login_required
def manage_subscription(request):
    stripe.api_key = settings.STRIPE_SECRET_KEY
    
    customer_id = request.user.profile.stripe_customer_id

    if not customer_id:
        messages.error(request, "Could not find a subscription for your account. Please contact support.")
        return redirect('account')
    
    try:
        portal_session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=request.build_absolute_uri(redirect('account').url),
        )
        return redirect(portal_session.url)
    except Exception as e:
        messages.error(request, f"An error occurred: {e}")
        return redirect('account')
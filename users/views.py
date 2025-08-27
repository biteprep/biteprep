# users/views.py
from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
import stripe
from .forms import CustomUserCreationForm
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.utils.decorators import method_decorator
from django.contrib.auth.views import LoginView
from axes.decorators import axes_dispatch
# REMOVED: from defender.decorators import watch_login
from django.core.exceptions import ValidationError
import logging

logger = logging.getLogger('security')

# Custom login view with rate limiting
class RateLimitedLoginView(LoginView):
    template_name = 'registration/login.html'
    
    @method_decorator(axes_dispatch)
    # REMOVED: @method_decorator(watch_login())
    @method_decorator(csrf_protect)
    @method_decorator(never_cache)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def form_invalid(self, form):
        # Log failed login attempt
        username = form.cleaned_data.get('username', 'unknown')
        ip = self.request.META.get('REMOTE_ADDR', 'unknown')
        logger.warning(f'Failed login attempt for {username} from {ip}')
        return super().form_invalid(form)

@csrf_protect
@never_cache
def signup(request):
    # Check if registration is disabled
    if hasattr(settings, 'REGISTRATION_OPEN') and not settings.REGISTRATION_OPEN:
        messages.error(request, "Registration is currently closed.")
        return redirect('home')
    
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        
        # Rate limiting check for registration
        ip = request.META.get('REMOTE_ADDR', '')
        cache_key = f'signup_attempt_{ip}'
        from django.core.cache import cache
        attempts = cache.get(cache_key, 0)
        
        if attempts >= 3:  # Max 3 registration attempts per hour
            messages.error(request, "Too many registration attempts. Please try again later.")
            return redirect('home')
        
        if form.is_valid():
            user = form.save()
            # Log successful registration
            logger.info(f'New user registered: {user.username} from IP {ip}')
            login(request, user)
            cache.delete(cache_key)  # Clear attempts on success
            return redirect('signup_success')
        else:
            # Increment failed attempts
            cache.set(cache_key, attempts + 1, 3600)  # 1 hour timeout
    else:
        form = CustomUserCreationForm()
    
    return render(request, 'registration/signup.html', {'form': form})

@login_required
def signup_success(request):
    return render(request, 'users/signup_success.html')

def logout_view(request):
    username = request.user.username if request.user.is_authenticated else 'anonymous'
    logout(request)
    logger.info(f'User {username} logged out')
    messages.info(request, "You have been successfully logged out.")
    return redirect('home')

@login_required
@csrf_protect
def account_page(request):
    # Check if user has profile (security check)
    if not hasattr(request.user, 'profile'):
        messages.error(request, "Profile not found. Please contact support.")
        return redirect('home')
    
    return render(request, 'users/account_page.html')

@login_required
@csrf_protect
def delete_account(request):
    if request.method == 'POST':
        # Require password confirmation for account deletion
        password = request.POST.get('confirm_password')
        
        if not request.user.check_password(password):
            messages.error(request, "Incorrect password. Account not deleted.")
            return redirect('account')
        
        user = request.user
        username = user.username
        logout(request)
        user.delete()
        
        logger.info(f'User {username} deleted their account')
        messages.success(request, "Your account has been successfully deleted.")
        return redirect('home')
    
    return redirect('account')

@login_required
@csrf_protect
def manage_subscription(request):
    stripe.api_key = settings.STRIPE_SECRET_KEY
    
    # Security check: verify user has profile with stripe customer ID
    if not hasattr(request.user, 'profile') or not request.user.profile.stripe_customer_id:
        messages.error(request, "Could not find a subscription for your account.")
        return redirect('account')
    
    customer_id = request.user.profile.stripe_customer_id
    
    try:
        portal_session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=request.build_absolute_uri(reverse('account')),
        )
        return redirect(portal_session.url)
    except Exception as e:
        logger.error(f"Stripe portal error for user {request.user.username}: {str(e)}")
        messages.error(request, "An error occurred accessing the subscription portal.")
        return redirect('account')
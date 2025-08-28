# users/views.py - PRODUCTION SECURE VERSION
from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.utils.decorators import method_decorator
from django.contrib.auth.views import LoginView
from django.core.exceptions import ValidationError
from django.core.cache import cache
from django.utils import timezone
from django.db import transaction
from django_ratelimit.decorators import ratelimit
import stripe
import logging
import hashlib
import secrets
from datetime import timedelta
from .forms import CustomUserCreationForm

# Security logger
security_logger = logging.getLogger('security')
logger = logging.getLogger(__name__)

def get_client_ip(request):
    """Securely get client IP address."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        # Take the first IP in the chain (client's real IP)
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '')
    return ip

def log_security_event(event_type, request, username=None, extra_data=None):
    """Log security-relevant events."""
    ip = get_client_ip(request)
    user_agent = request.META.get('HTTP_USER_AGENT', 'unknown')
    
    log_entry = {
        'event': event_type,
        'ip': ip,
        'user_agent': user_agent,
        'username': username or 'anonymous',
        'timestamp': timezone.now().isoformat(),
    }
    
    if extra_data:
        log_entry.update(extra_data)
    
    security_logger.info(f"Security Event: {log_entry}")

class SecureLoginView(LoginView):
    """Enhanced secure login view with rate limiting and security features."""
    template_name = 'registration/login.html'
    
    @method_decorator(ensure_csrf_cookie)
    @method_decorator(csrf_protect)
    @method_decorator(never_cache)
    @method_decorator(ratelimit(key='ip', rate='5/m', method='POST'))
    @method_decorator(ratelimit(key='post:username', rate='3/m', method='POST'))
    def dispatch(self, request, *args, **kwargs):
        # Check if already authenticated
        if request.user.is_authenticated:
            return redirect('dashboard')
        return super().dispatch(request, *args, **kwargs)
    
    def form_valid(self, form):
        """Handle successful login."""
        username = form.cleaned_data.get('username')
        
        # Log successful login
        log_security_event('successful_login', self.request, username)
        
        # Clear any failed login attempts from cache
        ip = get_client_ip(self.request)
        cache.delete(f'login_attempts_{ip}')
        cache.delete(f'login_attempts_{username}')
        
        # Set session security flags
        self.request.session.set_expiry(settings.SESSION_COOKIE_AGE)
        self.request.session['last_activity'] = timezone.now().isoformat()
        self.request.session['ip_address'] = ip
        
        messages.success(self.request, f"Welcome back, {username}!")
        return super().form_valid(form)
    
    def form_invalid(self, form):
        """Handle failed login attempt."""
        username = form.data.get('username', 'unknown')
        
        # Log failed attempt
        log_security_event('failed_login', self.request, username, {
            'errors': form.errors.as_json()
        })
        
        # Track failed attempts
        ip = get_client_ip(self.request)
        self._track_failed_attempt(ip, username)
        
        messages.error(
            self.request, 
            "Invalid credentials. Please check your username and password."
        )
        
        return super().form_invalid(form)
    
    def _track_failed_attempt(self, ip, username):
        """Track failed login attempts for security monitoring."""
        # Track by IP
        ip_key = f'login_attempts_{ip}'
        ip_attempts = cache.get(ip_key, 0)
        cache.set(ip_key, ip_attempts + 1, 3600)  # 1 hour
        
        # Track by username
        user_key = f'login_attempts_{username}'
        user_attempts = cache.get(user_key, 0)
        cache.set(user_key, user_attempts + 1, 3600)
        
        # Alert if threshold exceeded
        if ip_attempts >= 10:
            security_logger.warning(f"High failed login attempts from IP: {ip}")
        if user_attempts >= 5:
            security_logger.warning(f"High failed login attempts for user: {username}")

@csrf_protect
@never_cache
@ratelimit(key='ip', rate='3/h', method='POST')
def signup(request):
    """Secure signup view with rate limiting and validation."""
    # Check if registration is open
    if not getattr(settings, 'REGISTRATION_OPEN', True):
        messages.error(request, "Registration is currently closed.")
        return redirect('home')
    
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        
        if form.is_valid():
            try:
                with transaction.atomic():
                    user = form.save(commit=False)
                    
                    # Additional security checks
                    user.is_active = True
                    user.is_staff = False
                    user.is_superuser = False
                    user.save()
                    
                    # Log registration
                    log_security_event('user_registration', request, user.username, {
                        'email': user.email
                    })
                    
                    # Auto-login with session security
                    login(request, user)
                    request.session['registration_date'] = timezone.now().isoformat()
                    
                    messages.success(
                        request, 
                        "Account created successfully! Welcome to BitePrep."
                    )
                    
                    return redirect('signup_success')
                    
            except Exception as e:
                logger.error(f"Registration error: {str(e)}", exc_info=True)
                messages.error(request, "An error occurred during registration. Please try again.")
                form.add_error(None, "Registration failed. Please contact support if the problem persists.")
        else:
            # Log failed registration attempt
            log_security_event('failed_registration', request, extra_data={
                'errors': form.errors.as_json()
            })
    else:
        form = CustomUserCreationForm()
    
    return render(request, 'registration/signup.html', {'form': form})

@login_required
@never_cache
def signup_success(request):
    """Success page after registration."""
    # Verify this is a new registration
    if 'registration_date' not in request.session:
        return redirect('dashboard')
    
    # Clear the registration flag after displaying
    if timezone.now() - timezone.datetime.fromisoformat(request.session['registration_date']) > timedelta(minutes=5):
        del request.session['registration_date']
    
    return render(request, 'users/signup_success.html')

@login_required
@csrf_protect
@never_cache
def logout_view(request):
    """Secure logout with session cleanup."""
    username = request.user.username
    
    # Log logout event
    log_security_event('user_logout', request, username)
    
    # Clear session completely
    request.session.flush()
    
    # Perform logout
    logout(request)
    
    messages.info(request, "You have been successfully logged out.")
    return redirect('home')

@login_required
@csrf_protect
@never_cache
def account_page(request):
    """Secure account page."""
    # Verify session integrity
    if not _verify_session_integrity(request):
        messages.warning(request, "Session security check failed. Please log in again.")
        logout(request)
        return redirect('login')
    
    # Ensure profile exists
    if not hasattr(request.user, 'profile'):
        messages.error(request, "Account setup incomplete. Please contact support.")
        security_logger.error(f"Missing profile for user: {request.user.username}")
        return redirect('home')
    
    context = {
        'user': request.user,
        'profile': request.user.profile,
        'subscription_active': _check_subscription_status(request.user),
    }
    
    return render(request, 'users/account_page.html', context)

@login_required
@csrf_protect
@ratelimit(key='user', rate='3/h', method='POST')
def delete_account(request):
    """Secure account deletion with multiple confirmations."""
    if request.method == 'POST':
        # Require password confirmation
        password = request.POST.get('confirm_password', '')
        confirm_text = request.POST.get('confirm_delete', '')
        
        # Verify confirmation text
        if confirm_text != 'DELETE MY ACCOUNT':
            messages.error(request, "Please type 'DELETE MY ACCOUNT' to confirm.")
            return redirect('account')
        
        # Verify password
        if not request.user.check_password(password):
            messages.error(request, "Incorrect password. Account not deleted.")
            log_security_event('failed_account_deletion', request, request.user.username)
            return redirect('account')
        
        # Perform deletion
        user = request.user
        username = user.username
        user_id = user.id
        
        try:
            with transaction.atomic():
                # Cancel any active subscriptions first
                if hasattr(user, 'profile') and user.profile.stripe_customer_id:
                    _cancel_stripe_subscription(user.profile.stripe_customer_id)
                
                # Log deletion
                log_security_event('account_deleted', request, username, {
                    'user_id': user_id
                })
                
                # Delete user
                user.delete()
                
                # Logout
                logout(request)
                
                messages.success(request, "Your account has been permanently deleted.")
                return redirect('home')
                
        except Exception as e:
            logger.error(f"Account deletion error for user {username}: {str(e)}")
            messages.error(request, "An error occurred. Please contact support.")
            return redirect('account')
    
    return redirect('account')

@login_required
@csrf_protect
@ratelimit(key='user', rate='10/h')
def manage_subscription(request):
    """Secure Stripe subscription management."""
    if not _verify_session_integrity(request):
        logout(request)
        return redirect('login')
    
    stripe.api_key = settings.STRIPE_SECRET_KEY
    
    # Verify user has profile and customer ID
    if not hasattr(request.user, 'profile') or not request.user.profile.stripe_customer_id:
        messages.error(request, "No subscription found for your account.")
        return redirect('account')
    
    customer_id = request.user.profile.stripe_customer_id
    
    try:
        # Create portal session with additional security
        portal_session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=request.build_absolute_uri(reverse('account')),
            configuration=settings.STRIPE_PORTAL_CONFIG_ID if hasattr(settings, 'STRIPE_PORTAL_CONFIG_ID') else None,
        )
        
        # Log portal access
        log_security_event('stripe_portal_access', request, request.user.username, {
            'customer_id': customer_id
        })
        
        return redirect(portal_session.url)
        
    except stripe.error.StripeError as e:
        logger.error(f"Stripe portal error for user {request.user.username}: {str(e)}")
        messages.error(request, "Unable to access subscription management. Please try again later.")
        return redirect('account')

def _verify_session_integrity(request):
    """Verify session hasn't been hijacked."""
    current_ip = get_client_ip(request)
    session_ip = request.session.get('ip_address')
    
    # Check if IP has changed (potential session hijacking)
    if session_ip and session_ip != current_ip:
        security_logger.warning(f"Session IP mismatch for user {request.user.username}: {session_ip} != {current_ip}")
        return False
    
    # Check session age
    last_activity = request.session.get('last_activity')
    if last_activity:
        last_time = timezone.datetime.fromisoformat(last_activity)
        if timezone.now() - last_time > timedelta(hours=1):
            return False
    
    # Update last activity
    request.session['last_activity'] = timezone.now().isoformat()
    request.session['ip_address'] = current_ip
    
    return True

def _check_subscription_status(user):
    """Check if user has active subscription."""
    if not hasattr(user, 'profile'):
        return False
    
    profile = user.profile
    if profile.membership == 'Free':
        return False
    
    if profile.membership_expiry_date:
        return profile.membership_expiry_date >= timezone.now().date()
    
    return False

def _cancel_stripe_subscription(customer_id):
    """Cancel Stripe subscription when deleting account."""
    try:
        stripe.api_key = settings.STRIPE_SECRET_KEY
        subscriptions = stripe.Subscription.list(customer=customer_id, status='active')
        
        for subscription in subscriptions.auto_paging_iter():
            stripe.Subscription.delete(subscription.id)
            
    except Exception as e:
        logger.error(f"Error canceling Stripe subscription: {str(e)}")
# users/middleware.py

from .models import Profile
# No need to import 'resolve' here as we will let the view handle resolution.

class EnsureProfileMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Check if the user is authenticated and not an anonymous user
        if request.user.is_authenticated:
            # Use hasattr for a safe check, preventing an error if the profile doesn't exist
            if not hasattr(request.user, 'profile'):
                # If the profile does not exist, create it.
                Profile.objects.create(user=request.user)
        
        response = self.get_response(request)
        return response

class ForceProjectTemplateContextMiddleware:
    """
    Middleware to counteract context hijacking by django-otp or similar configurations.
    
    When OTPAdminSite is active, it (or related middleware) might set 
    request.current_app = 'admin'. This forces the template loader to look 
    only within the admin templates, even for standard auth views like 
    password_change.
    
    This middleware checks if the request is going to a standard auth path 
    and explicitly resets the current_app attribute, forcing the standard 
    template resolution.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Define the path prefix for standard authentication views
        # This should match the path used in the main urls.py (e.g., path('accounts/', ...))
        AUTH_URL_PREFIX = '/accounts/'

        if request.path.startswith(AUTH_URL_PREFIX):
            # If the request is for an auth view, ensure the context is not 'admin'
            if hasattr(request, 'current_app') and request.current_app == 'admin':
                # Resetting the current_app attribute forces default template resolution
                del request.current_app
        
        response = self.get_response(request)
        return response
# users/middleware.py

from .models import Profile

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
# users/middleware.py

# Assuming Profile model is imported from the users app models
# If Profile is defined elsewhere, adjust the import accordingly.
try:
    from .models import Profile
except ImportError:
    # Handle case where models might not be ready or defined yet
    Profile = None

class EnsureProfileMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Ensure Profile model is available before proceeding
        if Profile:
            # Check if the user is authenticated
            if request.user.is_authenticated:
                # Use hasattr for a quick check if the profile relation is already accessed/cached
                if not hasattr(request.user, 'profile'):
                    # Use get_or_create for robustness against race conditions
                    try:
                        Profile.objects.get_or_create(user=request.user)
                    except Exception as e:
                        # Log the error if profile creation fails (e.g., database issues)
                        # In a production environment, you might want to use a logger here
                        print(f"Error creating profile for user {getattr(request.user, 'id', 'N/A')}: {e}")
                        pass
        
        response = self.get_response(request)
        return response
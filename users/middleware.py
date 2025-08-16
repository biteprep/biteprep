# users/middleware.py

# Import ObjectDoesNotExist (crucial for the fix) and logging
from django.db.models import ObjectDoesNotExist
import logging

# Set up logger
logger = logging.getLogger(__name__)

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
        # Check if Profile model is available AND the user is authenticated
        if Profile and request.user.is_authenticated:
            try:
                # 1. Attempt to access the profile. 
                # If it exists, Django caches it and moves on.
                # We assign it to '_' because we don't need the object itself, just to trigger the lookup.
                _ = request.user.profile
            
            except ObjectDoesNotExist:
                # 2. If it does not exist, this specific exception is caught (instead of crashing).
                # Now we create it robustly using get_or_create.
                try:
                    Profile.objects.get_or_create(user=request.user)
                    # Log this event as it's often unexpected outside of the signup flow
                    logger.warning(f"Middleware created missing profile for user: {request.user.username} (ID: {request.user.id})")
                except Exception as e:
                    # Handle potential database errors during creation (e.g., race conditions, connection issues)
                    logger.error(f"CRITICAL: Error during Profile.get_or_create for user {request.user.id}: {e}", exc_info=True)
            
            except Exception as e:
                 # 3. Handle any other unexpected errors during profile access
                logger.error(f"Unexpected error accessing profile for user {request.user.id}: {e}", exc_info=True)

        
        response = self.get_response(request)
        return response
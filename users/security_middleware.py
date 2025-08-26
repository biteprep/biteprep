# users/security_middleware.py
import logging
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

security_logger = logging.getLogger('security')

@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    security_logger.info(f'Login: {user.username} from {get_client_ip(request)}')

@receiver(user_login_failed)
def log_user_login_failed(sender, credentials, request, **kwargs):
    security_logger.warning(f'Failed login: {credentials.get("username")} from {get_client_ip(request)}')

@receiver(user_logged_out)
def log_user_logout(sender, request, user, **kwargs):
    security_logger.info(f'Logout: {user.username} from {get_client_ip(request)}')

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip
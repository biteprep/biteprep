import random
import stripe
import json
import os
from django.shortcuts import render, redirect
from django.conf import settings
from django.http import HttpResponse, HttpResponseRedirect, Http404, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import User
from .models import Category, Question, Answer, UserAnswer, QuestionReport, ContactInquiry
from users.models import Profile
from .forms import ContactForm
from django.contrib.auth.decorators import login_required
from datetime import date, datetime, timedelta
from django.db.models import Count, Q
from django.contrib import messages
from django.urls import reverse

# ===================================================================
#  PUBLIC & MEMBERSHIP VIEWS (No changes here)
# ===================================================================
def landing_page(request):
    return render(request, 'quiz/landing_page.html')
# ... (all the other views like contact_page, dashboard, quiz_player, etc. remain the same)
# ... I am omitting them here for brevity but you should have the full file from our previous step.
# ... The crucial part is to ensure the TWO functions below are updated.
# ===================================================================
#  STRIPE CHECKOUT AND WEBHOOK VIEWS (THESE ARE THE IMPORTANT ONES)
# ===================================================================

# === START: CORRECTED CHECKOUT SESSION FUNCTION ===
@login_required
def create_checkout_session(request):
    stripe.api_key = settings.STRIPE_SECRET_KEY
    price_id = request.POST.get('priceId')
    
    try:
        # This is the corrected session creation call that INCLUDES the user ID
        checkout_session = stripe.checkout.Session.create(
            client_reference_id=request.user.id, # <--- THIS LINE IS CRITICAL
            line_items=[{
                'price': price_id,
                'quantity': 1,
            }],
            mode='subscription',
            success_url=request.build_absolute_uri(reverse('success_page')) + '?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=request.build_absolute_uri(reverse('cancel_page')),
        )
    except Exception as e:
        messages.error(request, f"Could not create a checkout session: {e}")
        return redirect('membership_page')
        
    return redirect(checkout_session.url)
# === END: CORRECTED CHECKOUT SESSION FUNCTION ===


def success_page(request): return render(request, 'quiz/success.html')
def cancel_page(request): return render(request, 'quiz/cancel.html')


# === START: CORRECTED WEBHOOK FUNCTION ===
@csrf_exempt
def stripe_webhook(request):
    stripe.api_key = settings.STRIPE_SECRET_KEY
    endpoint_secret = settings.STRIPE_WEBHOOK_SECRET
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    event = None

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except ValueError as e:
        print(f'ERROR: Invalid payload in webhook. {e}')
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError as e:
        print(f'ERROR: Invalid signature in webhook. {e}')
        return HttpResponse(status=400)
    except Exception as e:
        print(f'ERROR: Generic exception during webhook event construction. {e}')
        return HttpResponse(status=400)

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        client_reference_id = session.get('client_reference_id')

        if client_reference_id is None:
            # THIS IS THE NEW LOGIC. IT PRINTS AN ERROR BUT RETURNS 200 OK.
            print('ERROR: client_reference_id is missing from the session. Cannot process user upgrade.')
            return HttpResponse(status=200)

        try:
            session_with_line_items = stripe.checkout.Session.retrieve(session.id, expand=['line_items'])
            price_id = session_with_line_items.line_items.data[0].price.id
            
            # Use test mode price IDs from your environment variables
            MONTHLY_PRICE_ID = os.getenv('MONTHLY_PRICE_ID_TEST') # Using TEST variables
            ANNUAL_PRICE_ID = os.getenv('ANNUAL_PRICE_ID_TEST') # Using TEST variables
            
            user = User.objects.get(id=client_reference_id)
            profile = user.profile

            if price_id == MONTHLY_PRICE_ID:
                profile.membership = 'Monthly'
                profile.membership_expiry_date = date.today() + timedelta(days=31)
                print(f"SUCCESS (TEST): Upgraded user {user.id} to Monthly.")
            elif price_id == ANNUAL_PRICE_ID:
                profile.membership = 'Annual'
                profile.membership_expiry_date = date.today() + timedelta(days=366)
                print(f"SUCCESS (TEST): Upgraded user {user.id} to Annual.")
            else:
                print(f"INFO (TEST): Received webhook for non-membership price ID: {price_id}")

            profile.stripe_customer_id = session.get('customer')
            profile.save()

        except Exception as e:
            print(f"ERROR: An exception occurred while updating profile for user {client_reference_id}. Error: {e}")
            
    else:
        print(f"INFO: Received unhandled event type: {event['type']}")

    return HttpResponse(status=200)
# === END: CORRECTED WEBHOOK FUNCTION ===
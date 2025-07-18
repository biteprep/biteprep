# quiz/views.py

import random
import stripe
import json
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
from django.urls import reverse # Add this import for the fix

# ===================================================================
#  PUBLIC & MEMBERSHIP VIEWS
# ===================================================================

def landing_page(request):
    return render(request, 'quiz/landing_page.html')

def contact_page(request):
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Thank you for your message! We will get back to you shortly.")
            return redirect('home')
    else:
        if request.user.is_authenticated:
            initial_data = {'name': request.user.username, 'email': request.user.email}
            form = ContactForm(initial=initial_data)
        else:
            form = ContactForm()
            
    return render(request, 'quiz/contact_page.html', {'form': form})

def subscription_required(function):
    def wrapper(request, *args, **kwargs):
        if request.user.is_authenticated and hasattr(request.user, 'profile'):
            profile = request.user.profile
            if (profile.membership != 'Free' and
                profile.membership_expiry_date and
                profile.membership_expiry_date >= date.today()):
                return function(request, *args, **kwargs)
        messages.warning(request, "Access to this feature requires an active subscription. Please choose a plan to continue.")
        return redirect('membership_page')
    return wrapper

@login_required
def membership_page(request):
    return render(request, 'quiz/membership_page.html')

@login_required
def dashboard(request):
    user_answers = UserAnswer.objects.filter(user=request.user)
    total_answered = user_answers.count()
    correct_answered = user_answers.filter(is_correct=True).count()
    try:
        overall_percentage = (correct_answered / total_answered) * 100
    except ZeroDivisionError:
        overall_percentage = 0
    topic_performance = (
        UserAnswer.objects.filter(user=request.user)
        .values('question__subtopic__topic__name')
        .annotate(total=Count('id'), correct=Count('id', filter=Q(is_correct=True)))
        .order_by('-total')
    )
    topic_stats = []
    for topic in topic_performance:
        try:
            percentage = (topic['correct'] / topic['total']) * 100
        except ZeroDivisionError:
            percentage = 0
        topic_stats.append({'name': topic['question__subtopic__topic__name'], 'total': topic['total'], 'correct': topic['correct'], 'percentage': round(percentage, 1)})
    context = {
        'total_answered': total_answered,
        'correct_answered': correct_answered,
        'overall_percentage': round(overall_percentage, 1),
        'topic_stats': topic_stats,
    }
    return render(request, 'quiz/dashboard.html', context)

@login_required
def reset_performance(request):
    if request.method == 'POST':
        UserAnswer.objects.filter(user=request.user).delete()
        messages.success(request, "Your performance statistics have been successfully reset.")
        return redirect('dashboard')
    return redirect('dashboard')


# ===================================================================
#  QUIZ ENGINE VIEWS
# ===================================================================

@login_required
def quiz_setup(request):
    if not hasattr(request.user, 'profile'):
        Profile.objects.create(user=request.user)
    
    if request.method == 'POST':
        profile = request.user.profile
        if (profile.membership == 'Free' or 
            (profile.membership_expiry_date and profile.membership_expiry_date >= date.today())):
            pass
        else:
            messages.warning(request, "Your subscription has expired. Please renew your plan to continue.")
            return redirect('membership_page')

        selected_subtopic_ids = request.POST.getlist('subtopics')
        question_count_type = request.POST.get('question_count_type', 'all')
        question_filter = request.POST.get('question_filter', 'all')
        quiz_mode = request.POST.get('quiz_mode', 'quiz')
        timer_minutes = 0
        if 'timer-toggle' in request.POST:
            try: timer_minutes = int(request.POST.get('timer_minutes', 0))
            except (ValueError, TypeError): timer_minutes = 0
        penalty_value = 0.0
        if 'negative-marking-toggle' in request.POST:
            try: penalty_value = float(request.POST.get('penalty_value', 0.0))
            except (ValueError, TypeError): penalty_value = 0.0

        if not selected_subtopic_ids:
            messages.info(request, "Please select at least one topic to start a quiz.")
            return redirect('quiz_setup')

        questions = Question.objects.filter(subtopic__id__in=selected_subtopic_ids)

        if question_filter == 'unanswered':
            answered_question_ids = UserAnswer.objects.filter(user=request.user).values_list('question_id', flat=True)
            questions = questions.exclude(id__in=answered_question_ids)
        elif question_filter == 'correct':
            correctly_answered_ids = UserAnswer.objects.filter(user=request.user, is_correct=True).values_list('question_id', flat=True)
            questions = questions.filter(id__in=correctly_answered_ids)
        elif question_filter == 'incorrect':
            incorrectly_answered_ids = UserAnswer.objects.filter(user=request.user, is_correct=False).values_list('question_id', flat=True)
            questions = questions.filter(id__in=incorrectly_answered_ids)
        
        question_ids = list(questions.values_list('id', flat=True))
        random.shuffle(question_ids)
        
        if request.user.profile.membership == 'Free':
            FREE_TIER_LIMIT = 10
            if len(question_ids) > FREE_TIER_LIMIT:
                question_ids = question_ids[:FREE_TIER_LIMIT]
                messages.info(request, f"Your quiz has been limited to {FREE_TIER_LIMIT} questions for the free trial. Upgrade to unlock unlimited access!")
            if question_count_type == 'custom':
                try:
                    custom_count = int(request.POST.get('question_count_custom', FREE_TIER_LIMIT))
                    if custom_count > FREE_TIER_LIMIT:
                        question_ids = question_ids[:FREE_TIER_LIMIT]
                except (ValueError, TypeError):
                    pass
        elif question_count_type == 'custom':
            try:
                custom_count = int(request.POST.get('question_count_custom', 10))
                if custom_count > 0:
                    question_ids = question_ids[:custom_count]
            except (ValueError, TypeError):
                pass
        
        if not question_ids:
            messages.info(request, "No questions found for your selected topics and filters.")
            return redirect('quiz_setup')
            
        quiz_context = {
            'question_ids': question_ids, 'total_questions': len(question_ids), 'mode': quiz_mode,
            'penalty': penalty_value, 'user_answers': {}, 'flagged_questions': [],
        }
        if timer_minutes > 0:
            quiz_context['start_time'] = datetime.now().isoformat()
            quiz_context['duration_seconds'] = timer_minutes * 60
        request.session['quiz_context'] = quiz_context
        return redirect('start_quiz')
        
    categories = Category.objects.prefetch_related('topics__subtopics').all()
    context = {'categories': categories}
    return render(request, 'quiz/quiz_setup.html', context)

@login_required
def start_quiz(request):
    if 'quiz_context' in request.session:
        request.session['quiz_context']['user_answers'] = {}
        request.session['quiz_context']['flagged_questions'] = []
        request.session.modified = True
        return redirect('quiz_player', question_index=1)
    messages.error(request, "Could not start quiz. Please try setting it up again.")
    return redirect('quiz_setup')

@login_required
def quiz_player(request, question_index):
    if 'quiz_context' not in request.session:
        messages.error(request, "Quiz session not found. Please start a new quiz.")
        return redirect('quiz_setup')

    quiz_context = request.session['quiz_context']
    question_ids = quiz_context.get('question_ids', [])
    quiz_mode = quiz_context.get('mode', 'quiz')

    if 'start_time' in quiz_context:
        start_time = datetime.fromisoformat(quiz_context['start_time'])
        duration = timedelta(seconds=quiz_context.get('duration_seconds', 0))
        if datetime.now() > start_time + duration:
            messages.info(request, "Time is up! The quiz has been automatically submitted.")
            return redirect('quiz_results')
            
    if not (0 < question_index <= len(question_ids)):
        return redirect('quiz_results')

    question_id = question_ids[question_index - 1]
    
    if request.method == 'POST':
        submitted_answer_id = request.POST.get('answer')
        if submitted_answer_id:
            quiz_context['user_answers'][str(question_id)] = int(submitted_answer_id)

        action = request.POST.get('action')

        if action == 'toggle_flag':
            flagged = quiz_context.get('flagged_questions', [])
            if question_id in flagged:
                flagged.remove(question_id)
            else:
                flagged.append(question_id)
            quiz_context['flagged_questions'] = flagged
            request.session.modified = True
            return redirect('quiz_player', question_index=question_index)
        
        elif action == 'prev' and question_index > 1:
            request.session.modified = True
            return redirect('quiz_player', question_index=question_index - 1)

        elif action == 'next' and question_index < len(question_ids):
            request.session.modified = True
            return redirect('quiz_player', question_index=question_index + 1)

        elif action == 'finish':
            request.session.modified = True
            return redirect('quiz_results')

        elif action == 'submit_answer' and quiz_mode == 'quiz':
            if not submitted_answer_id:
                messages.warning(request, "Please select an answer before submitting.")
                return redirect('quiz_player', question_index=question_index)

            request.session.modified = True
            question = Question.objects.get(pk=question_id)
            user_answer_obj = Answer.objects.get(pk=int(submitted_answer_id))
            
            context = {
                'question': question, 'question_index': question_index, 'total_questions': len(question_ids),
                'quiz_context': quiz_context, 'is_feedback_mode': True, 'user_answer': user_answer_obj,
                'is_last_question': question_index == len(question_ids), 'seconds_remaining': None
            }
            return render(request, 'quiz/quiz_player.html', context)
        
        request.session.modified = True
        return redirect('quiz_player', question_index=question_index)

    question = Question.objects.select_related('subtopic__topic').prefetch_related('answers').get(pk=question_id)
    seconds_remaining = None
    if 'start_time' in quiz_context:
        start_time = datetime.fromisoformat(quiz_context['start_time'])
        duration = timedelta(seconds=quiz_context.get('duration_seconds', 0))
        time_passed = datetime.now() - start_time
        seconds_remaining = max(0, int((duration - time_passed).total_seconds()))

    context = {
        'question': question, 'question_index': question_index, 'total_questions': len(question_ids),
        'quiz_context': quiz_context, 'is_feedback_mode': False,
        'user_selected_answer_id': quiz_context.get('user_answers', {}).get(str(question_id)),
        'seconds_remaining': seconds_remaining
    }
    return render(request, 'quiz/quiz_player.html', context)


@login_required
def quiz_results(request):
    if 'quiz_context' not in request.session:
        return redirect('home')

    quiz_context = request.session.pop('quiz_context')
    user_answers_dict = quiz_context.get('user_answers', {})
    question_ids = quiz_context.get('question_ids', [])
    penalty = quiz_context.get('penalty', 0.0)

    final_score = 0.0
    questions_in_quiz = Question.objects.filter(pk__in=question_ids).prefetch_related('answers')
    question_map = {q.id: q for q in questions_in_quiz}
    
    for q_id_str, user_answer_id in user_answers_dict.items():
        q_id = int(q_id_str)
        question = question_map.get(q_id)
        if question:
            answer = next((ans for ans in question.answers.all() if ans.id == user_answer_id), None)
            if answer:
                UserAnswer.objects.update_or_create(
                    user=request.user,
                    question=question,
                    defaults={'is_correct': answer.is_correct}
                )
                if answer.is_correct:
                    final_score += 1.0
                else:
                    final_score -= penalty

    total_questions = len(question_ids)
    try:
        percentage_score = (final_score / total_questions) * 100 if total_questions > 0 else 0
    except ZeroDivisionError:
        percentage_score = 0

    review_data = []
    for q_id in question_ids:
        question = question_map.get(q_id)
        if question:
            user_answer_id = user_answers_dict.get(str(q_id))
            user_answer = next((ans for ans in question.answers.all() if ans.id == user_answer_id), None) if user_answer_id else None
            review_data.append({'question': question, 'user_answer': user_answer})

    context = {
        'final_score': round(final_score, 2),
        'total_questions': total_questions,
        'percentage_score': round(percentage_score, 2),
        'review_data': review_data
    }
    
    return render(request, 'quiz/quiz_review.html', context)

@login_required
def report_question(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            question_id = data.get('question_id')
            reason = data.get('reason')

            if not question_id or not reason:
                return JsonResponse({'status': 'error', 'message': 'Missing data.'}, status=400)
            
            question = Question.objects.get(pk=question_id)
            
            report, created = QuestionReport.objects.update_or_create(
                user=request.user,
                question=question,
                defaults={'reason': reason, 'status': 'OPEN'}
            )
            
            return JsonResponse({'status': 'success', 'message': 'Report submitted successfully!'})
        
        except Question.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Question not found.'}, status=404)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)

# ===================================================================
#  STRIPE CHECKOUT AND WEBHOOK VIEWS
# ===================================================================
@login_required
def create_checkout_session(request):
    stripe.api_key = settings.STRIPE_SECRET_KEY
    price_id = request.POST.get('priceId')
    
    try:
        # This is the corrected session creation call with the user ID
        checkout_session = stripe.checkout.Session.create(
            client_reference_id=request.user.id,
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

def success_page(request): return render(request, 'quiz/success.html')
def cancel_page(request): return render(request, 'quiz/cancel.html')

@csrf_exempt
def stripe_webhook(request):
    endpoint_secret = settings.STRIPE_WEBHOOK_SECRET
    payload = request.body
    sig_header = request.META['HTTP_STRIPE_SIGNATURE']
    event = None
    try: event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except ValueError as e: return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError as e: return HttpResponse(status=400)
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        try:
            user_id = session.client_reference_id
            if user_id is None: return HttpResponse('Error: No user ID in session', status=400)
            
            session_with_line_items = stripe.checkout.Session.retrieve(session.id, expand=['line_items'])
            price_id = session_with_line_items.line_items.data[0].price.id

            user = User.objects.get(id=user_id)
            profile = user.profile
            
            profile.stripe_customer_id = session.customer

            if price_id == 'price_1RkrOp2Y8UHHjO4s3j7nZ29G':
                profile.membership = 'Monthly'; profile.membership_expiry_date = date.today() + timedelta(days=31)
            elif price_id == 'price_1RkrR12Y8UHHjO4srz9JbCin':
                profile.membership = 'Annual'; profile.membership_expiry_date = date.today() + timedelta(days=366)
            
            profile.save()

        except User.DoesNotExist: return HttpResponse('Error: User not found', status=404)
        except Exception as e: return HttpResponse(f"Error: {e}", status=500)
    return HttpResponse(status=200)
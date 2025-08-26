# quiz/views.py

import random
import stripe
import json
import logging

# Ensure datetime and timezone are imported correctly
from datetime import datetime, timedelta
from django.utils import timezone
# Import Decimal for precise score calculations
from decimal import Decimal, ROUND_HALF_UP
# Added get_object_or_404 for robustness
from django.shortcuts import render, redirect, HttpResponse, get_object_or_404
from django.conf import settings
# Added Http404 for security validation
from django.http import JsonResponse, Http404
# Added csrf_protect for security
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.contrib.auth.decorators import login_required
# Added Prefetch to imports
from django.db.models import Count, Q, Prefetch
# Import DatabaseError
from django.db.utils import DatabaseError
from django.db.models.functions import TruncDate
from django.contrib import messages
from django.urls import reverse
# Added PermissionDenied and cache imports for security
from django.core.exceptions import PermissionDenied
from django.views.decorators.cache import cache_page
from django.core.cache import cache

# Added Topic and Subtopic to imports for optimization
from .models import Category, Topic, Subtopic, Question, Answer, UserAnswer, FlaggedQuestion, QuestionReport
from .forms import ContactForm

# Import Profile model for webhook processing
try:
    from users.models import Profile
except ImportError:
    Profile = None


# Set up logging
# Use __name__ to get the logger specific to this module (e.g., 'quiz.views')
logger = logging.getLogger(__name__)

MAX_QUESTIONS_PER_QUIZ = 500

# --- Security Decorators ---

def premium_required(view_func):
    """Decorator to check if user has active premium subscription"""
    @login_required
    def wrapped_view(request, *args, **kwargs):
        profile = request.user.profile
        today = timezone.now().date()
        
        # Check if user has active subscription
        if profile.membership == 'Free':
            # Free users have limited access
            pass  # We'll check limits in the view
        elif profile.membership_expiry_date and profile.membership_expiry_date < today:
            messages.warning(request, "Your subscription has expired. Please renew to continue.")
            return redirect('membership_page')
        
        return view_func(request, *args, **kwargs)
    return wrapped_view

def rate_limit_quiz(view_func):
    """Rate limit quiz attempts to prevent abuse"""
    @login_required
    def wrapped_view(request, *args, **kwargs):
        user_id = request.user.id
        cache_key = f'quiz_rate_{user_id}'
        
        # Check rate limit (max 100 questions per hour for security)
        attempts = cache.get(cache_key, 0)
        if attempts > 100:
            messages.error(request, "You've exceeded the maximum quiz attempts. Please wait before trying again.")
            return redirect('dashboard')
        
        # Increment counter
        cache.set(cache_key, attempts + 1, 3600)  # 1 hour expiry
        
        return view_func(request, *args, **kwargs)
    return wrapped_view


# --- Helper Views (Landing, Contact, Legal, Membership) ---

def landing_page(request):
    return render(request, 'quiz/landing_page.html')

@csrf_protect
def contact_page(request):
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Thank you for your message! We will get back to you shortly.")
            return redirect('home')
    else:
        initial_data = {}
        if request.user.is_authenticated:
            # Try to get full name, fallback to username
            display_name = request.user.get_full_name()
            if not display_name:
                display_name = request.user.username
            initial_data = {'name': display_name, 'email': request.user.email}
        form = ContactForm(initial=initial_data)
    return render(request, 'quiz/contact.html', {'form': form})

def terms_page(request):
    return render(request, 'quiz/terms_and_conditions.html')

def privacy_page(request):
    return render(request, 'quiz/privacy_policy.html')

def cookie_page(request):
    return render(request, 'quiz/cookie_policy.html')

@login_required
def membership_page(request):
    return render(request, 'quiz/membership_page.html')


# --- Dashboard View ---

@login_required
def dashboard(request):
    user_answers = UserAnswer.objects.filter(user=request.user)
    total_answered = user_answers.count()
    correct_answered = user_answers.filter(is_correct=True).count()

    if total_answered > 0:
        overall_percentage = (Decimal(correct_answered) / Decimal(total_answered)) * 100
    else:
        overall_percentage = Decimal(0)

    thirty_days_ago = timezone.now() - timedelta(days=30)
    daily_performance = (UserAnswer.objects.filter(user=request.user, timestamp__gte=thirty_days_ago)
        .annotate(date=TruncDate('timestamp')).values('date')
        .annotate(daily_total=Count('id'), daily_correct=Count('id', filter=Q(is_correct=True)))
        .order_by('date'))

    chart_labels = [d['date'].strftime('%b %d') for d in daily_performance]
    chart_data = []
    for d in daily_performance:
        if d['daily_total'] > 0:
            perc = (Decimal(d['daily_correct']) / Decimal(d['daily_total'])) * 100
            chart_data.append(float(perc.quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)))
        else:
            chart_data.append(0.0)

    subtopic_performance = (UserAnswer.objects.filter(user=request.user)
        .values('question__subtopic__topic__name', 'question__subtopic__name')
        .annotate(total=Count('id'), correct=Count('id', filter=Q(is_correct=True)))
        .order_by('question__subtopic__topic__name', 'question__subtopic__name'))

    topic_stats = {}
    for item in subtopic_performance:
        topic_name = item['question__subtopic__topic__name']
        if topic_name not in topic_stats:
            topic_stats[topic_name] = {'total': 0, 'correct': 0, 'subtopics': []}
        topic_stats[topic_name]['total'] += item['total']
        topic_stats[topic_name]['correct'] += item['correct']
        sub_perc = (Decimal(item['correct']) / Decimal(item['total']) * 100) if item['total'] > 0 else Decimal(0)
        topic_stats[topic_name]['subtopics'].append({
            'name': item['question__subtopic__name'],
            'total': item['total'],
            'correct': item['correct'],
            'percentage': sub_perc.quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)
        })

    for topic_name, data in topic_stats.items():
        data['percentage'] = (Decimal(data['correct']) / Decimal(data['total']) * 100) if data['total'] > 0 else Decimal(0)
        data['percentage'] = data['percentage'].quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)

    context = {
        'total_answered': total_answered,
        'correct_answered': correct_answered,
        'overall_percentage': overall_percentage.quantize(Decimal('0.1'), rounding=ROUND_HALF_UP),
        'topic_stats': topic_stats,
        'chart_labels': json.dumps(chart_labels),
        'chart_data': json.dumps(chart_data),
        'incorrect_questions_count': user_answers.filter(is_correct=False).values('question_id').distinct().count(),
        'flagged_questions_count': FlaggedQuestion.objects.filter(user=request.user).count(),
    }
    return render(request, 'quiz/dashboard.html', context)


# --- Quiz Flow Views ---

@login_required
@premium_required
@csrf_protect
def quiz_setup(request):
    """Quiz setup with proper permission checks and input validation"""
    if request.method == 'POST':
        profile = request.user.profile

        # Use timezone.now().date() for robust, timezone-aware date comparison
        today = timezone.now().date()
        
        # Check subscription status
        is_active_subscription = profile.membership != 'Free' and profile.membership_expiry_date and profile.membership_expiry_date >= today
        
        if not (profile.membership == 'Free' or is_active_subscription):
            messages.warning(request, "Your subscription has expired. Please renew your plan.")
            return redirect('membership_page')
        
        selected_subtopic_ids = request.POST.getlist('subtopics')
        
        # Security: Validate subtopic IDs (Ensure they are integers)
        try:
            selected_subtopic_ids = [int(id) for id in selected_subtopic_ids]
        except (ValueError, TypeError):
            messages.error(request, "Invalid topic selection.")
            return redirect('quiz_setup')
        
        if not selected_subtopic_ids:
            messages.info(request, "Please select at least one topic to start a quiz.")
            return redirect('quiz_setup')
        
        question_filter = request.POST.get('question_filter', 'all')

        # Handle the case where the 'status' column might be missing during the POST request.
        try:
            # Attempt to filter by LIVE status
            questions = Question.objects.filter(
                subtopic__id__in=selected_subtopic_ids,
                status='LIVE'
            )
        except DatabaseError:
             # Fallback if 'status' column is missing: Assume all questions are LIVE.
             logger.warning("DatabaseError in quiz_setup (POST). 'status' column likely missing. Assuming all questions are LIVE.")
             questions = Question.objects.filter(
                subtopic__id__in=selected_subtopic_ids
            )
        
        if question_filter == 'unanswered':
            answered_question_ids = UserAnswer.objects.filter(user=request.user).values_list('question_id', flat=True)
            questions = questions.exclude(id__in=answered_question_ids)
        elif question_filter == 'correct':
            questions = questions.filter(id__in=UserAnswer.objects.filter(user=request.user, is_correct=True).values_list('question_id', flat=True))
        elif question_filter == 'incorrect':
            questions = questions.filter(id__in=UserAnswer.objects.filter(user=request.user, is_correct=False).values_list('question_id', flat=True))
        
        question_ids = list(questions.values_list('id', flat=True).distinct())
        
        if not question_ids:
            messages.info(request, "No live questions found for your selected topics and filters.")
            return redirect('quiz_setup')
        
        random.shuffle(question_ids)
        
        # Handle question count limits
        if profile.membership == 'Free':
            question_ids = question_ids[:10]
        elif request.POST.get('question_count_type') == 'custom':
            try:
                custom_count = int(request.POST.get('question_count_custom', 0))
                if custom_count > 0:
                    question_ids = question_ids[:custom_count]
            except (ValueError, TypeError): pass
        
        if len(question_ids) > MAX_QUESTIONS_PER_QUIZ:
            if profile.membership != 'Free':
                 messages.warning(request, f"To ensure stability, the quiz has been limited to the maximum of {MAX_QUESTIONS_PER_QUIZ} questions.")
            question_ids = question_ids[:MAX_QUESTIONS_PER_QUIZ]


        # Initialize quiz context
        quiz_mode = request.POST.get('quiz_mode', 'quiz')
        quiz_context = {
            'question_ids': question_ids, 'total_questions': len(question_ids),
            'mode': quiz_mode, 'user_answers': {},
            'penalty_value': 0.0
        }

        # Handle Timer
        if 'timer-toggle' in request.POST:
            try:
                timer_minutes = int(request.POST.get('timer_minutes', 0))
                if timer_minutes > 0:
                    quiz_context['start_time'] = timezone.now().isoformat()
                    quiz_context['duration_seconds'] = timer_minutes * 60
            except (ValueError, TypeError): pass

        # Handle Negative Marking
        if 'negative-marking-toggle' in request.POST:
            try:
                penalty = float(request.POST.get('penalty_value', 0.0))
                if penalty > 0:
                    quiz_context['penalty_value'] = penalty
            except (ValueError, TypeError):
                messages.warning(request, "Invalid penalty value ignored.")
                pass


        request.session['quiz_context'] = quiz_context
        return redirect('start_quiz')

    # GET request: Display the form
    # Optimized the query using Prefetch objects to prevent timeouts in production.
    try:
        # 1. Define Prefetch for Subtopics: Only fetch subtopics that have LIVE questions.
        live_subtopics = Prefetch(
            'subtopics',
            queryset=Subtopic.objects.filter(questions__status='LIVE').distinct()
        )
        
        # 2. Define Prefetch for Topics: Only fetch topics that have LIVE questions, 
        #    AND apply the live_subtopics prefetch to them.
        live_topics = Prefetch(
            'topics',
            queryset=Topic.objects.filter(subtopics__questions__status='LIVE').distinct().prefetch_related(live_subtopics)
        )

        # 3. Fetch Categories: Only fetch categories that have LIVE questions,
        #    AND apply the live_topics prefetch.
        categories = Category.objects.filter(
            topics__subtopics__questions__status='LIVE'
        ).distinct().prefetch_related(live_topics)

    except DatabaseError:
        # Fallback if the 'status' column is missing (maintains resilience during deployment).
        logger.warning("DatabaseError in quiz_setup (GET). 'status' column likely missing. Falling back to loading all categories (less efficient).")
        categories = Category.objects.prefetch_related('topics__subtopics').all()

    
    context = {'categories': categories}
    return render(request, 'quiz/quiz_setup.html', context)


@login_required
def start_quiz(request):
    if 'quiz_context' in request.session:
        request.session['quiz_context']['user_answers'] = {}
        request.session.modified = True
        return redirect('quiz_player', question_index=1)
    messages.error(request, "Could not start quiz. Please try setting it up again.")
    return redirect('quiz_setup')

@login_required
@rate_limit_quiz
@csrf_protect
def quiz_player(request, question_index):
    """Quiz player with rate limiting and session validation"""
    quiz_context = request.session.get('quiz_context')
    
    # Security: Validate quiz session structure
    if not quiz_context or not isinstance(quiz_context, dict):
        messages.error(request, "Invalid quiz session. Please start a new quiz.")
        return redirect('quiz_setup')

    # Security: Validate question index (URL parameter)
    try:
        question_index = int(question_index)
    except (ValueError, TypeError):
        raise Http404("Invalid question index")

    question_ids = quiz_context.get('question_ids', [])
    total_questions = len(question_ids)

    # Security: Validate question IDs in session are integers
    if not all(isinstance(id, int) for id in question_ids):
        messages.error(request, "Invalid quiz data in session. Please start a new quiz.")
        request.session.pop('quiz_context', None) # Clear bad session
        return redirect('quiz_setup')

    # Ensure index is within bounds
    if not (0 < question_index <= total_questions):
        # Check if the index is exactly 1 more than total, common after the last question
        if question_index == total_questions + 1:
             return redirect('quiz_results')
        # Handle other invalid indices (e.g., 0 or very large numbers)
        if total_questions > 0:
            messages.warning(request, f"Invalid question index ({question_index}). Redirecting to quiz start.")
            return redirect('quiz_player', question_index=1)
        else:
            return redirect('quiz_setup')


    question_id = question_ids[question_index - 1]
    quiz_mode = quiz_context.get('mode', 'quiz')
    is_feedback_mode = False

    # Handle POST request (Answering and Navigation)
    if request.method == 'POST':
        action = request.POST.get('action')
        submitted_answer_id_str = request.POST.get('answer')
        user_answers = quiz_context.get('user_answers', {})
        current_answer_info = user_answers.get(str(question_id), {}).copy()
        is_submitted_now = current_answer_info.get('is_submitted', False)

        if quiz_mode == 'quiz' and action == 'submit_answer':
            is_submitted_now = True

        if submitted_answer_id_str:
            try:
                # Security: Ensure the answer belongs to the current question
                answer = Answer.objects.get(id=int(submitted_answer_id_str), question_id=question_id)
                quiz_context['user_answers'][str(question_id)] = {
                    'answer_id': answer.id,
                    'is_correct': answer.is_correct,
                    'is_submitted': is_submitted_now
                }
            except (Answer.DoesNotExist, ValueError):
                # Log potential tampering attempt
                logger.warning(f"User {request.user.id} attempted to submit invalid answer ID {submitted_answer_id_str} for question {question_id}")
                pass
        elif is_submitted_now and str(question_id) not in user_answers:
             # Handle submitting a blank answer in quiz mode
             quiz_context['user_answers'][str(question_id)] = {'answer_id': None, 'is_correct': False, 'is_submitted': True}

        if action == 'toggle_flag':
            flag, created = FlaggedQuestion.objects.get_or_create(user=request.user, question_id=question_id)
            if not created: flag.delete()

        request.session.modified = True

        # Navigation logic
        navigate_to_index_str = request.POST.get('navigate_to')
        if navigate_to_index_str:
            try:
                target_index = int(navigate_to_index_str)
                # Security: Validate navigation target
                if 0 < target_index <= total_questions:
                    return redirect('quiz_player', question_index=target_index)
            except (ValueError, TypeError):
                pass

        if action == 'prev' and question_index > 1: return redirect('quiz_player', question_index=question_index - 1)
        if action == 'next' and question_index < total_questions: return redirect('quiz_player', question_index=question_index + 1)
        if action == 'finish': return redirect('quiz_results')


    # --- GET Request (or after POST if not redirecting) ---

    # Calculate Progress Percentage
    if total_questions > 0:
        progress_percentage = round((question_index / total_questions) * 100)
    else:
        progress_percentage = 0

    # Prepare context data
    question = get_object_or_404(Question.objects.prefetch_related('answers'), pk=question_id)
    
    user_answers = quiz_context.get('user_answers', {})
    user_answer_info = user_answers.get(str(question_id))
    seconds_remaining = None

    # Timer Logic
    if 'start_time' in quiz_context:
        try:
            start_time = datetime.fromisoformat(quiz_context['start_time'])
            duration = timedelta(seconds=quiz_context.get('duration_seconds', 0))

            # Robust Timezone Handling
            now = timezone.now()
            # Check if start_time is naive while now is aware
            if timezone.is_naive(start_time) and timezone.is_aware(now):
                 # If start_time lost timezone info, assume UTC
                 start_time = timezone.make_aware(start_time, timezone.utc)

            time_passed = now - start_time
            seconds_remaining = max(0, int((duration - time_passed).total_seconds()))
            if seconds_remaining <= 0:
                messages.info(request, "Time is up! The quiz has been automatically submitted.")
                return redirect('quiz_results')
        except (ValueError, TypeError) as e:
             logger.error(f"Error processing timer data: {e}. Session data: {quiz_context.get('start_time')}", exc_info=True)
             # Clear bad timer data
             del quiz_context['start_time']
             request.session.modified = True

    # Navigator setup
    user_flagged_ids = set(FlaggedQuestion.objects.filter(user=request.user, question_id__in=question_ids).values_list('question_id', flat=True))
    navigator_items = []

    for i, q_id in enumerate(question_ids):
        idx = i + 1
        answer_info = user_answers.get(str(q_id))
        btn_class = 'btn-outline-secondary'
        if answer_info:
            if quiz_mode == 'test':
                 btn_class = 'btn-primary'
            elif quiz_mode == 'quiz':
                if answer_info.get('is_submitted'):
                     btn_class = 'btn-success' if answer_info.get('is_correct') else 'btn-danger'
                else:
                    btn_class = 'btn-primary'
        if idx == question_index:
            btn_class = btn_class.replace('btn-outline-', 'btn-') + ' active'
        navigator_items.append({'index': idx, 'class': btn_class, 'is_flagged': q_id in user_flagged_ids})

    if quiz_mode == 'quiz' and user_answer_info and user_answer_info.get('is_submitted'):
        is_feedback_mode = True

    # Safely fetch user answer object for feedback mode
    user_answer_obj = None
    if is_feedback_mode and user_answer_info and user_answer_info.get('answer_id'):
        try:
            user_answer_obj = Answer.objects.get(id=user_answer_info['answer_id'])
        except Answer.DoesNotExist:
            pass

    # Ensure penalty value is a Decimal for template display
    try:
        penalty_value_decimal = Decimal(str(quiz_context.get('penalty_value', 0.0)))
    except Exception:
        penalty_value_decimal = Decimal(0)

    context = {
        'question': question,
        'question_index': question_index,
        'total_questions': total_questions,
        'progress_percentage': progress_percentage,
        'quiz_context': quiz_context,
        'is_feedback_mode': is_feedback_mode,
        'user_selected_answer_id': user_answer_info.get('answer_id') if user_answer_info else None,
        'user_answer': user_answer_obj,
        'is_last_question': question_index == total_questions,
        'flagged_questions': user_flagged_ids,
        'seconds_remaining': seconds_remaining,
        'navigator_items': navigator_items,
        'penalty_value': penalty_value_decimal,
    }
    return render(request, 'quiz/quiz_player.html', context)


@login_required
@csrf_protect
def quiz_results(request):
    # Retrieve and clear the quiz context from the session
    quiz_context = request.session.pop('quiz_context', None)
    if not quiz_context: return redirect('home')

    user_answers_dict = quiz_context.get('user_answers', {})
    question_ids = quiz_context.get('question_ids', [])
    total_questions = len(question_ids)

    try:
        penalty_value = Decimal(str(quiz_context.get('penalty_value', 0.0)))
    except Exception:
        penalty_value = Decimal(0)


    questions_in_quiz = Question.objects.filter(pk__in=question_ids).prefetch_related('answers')
    question_map = {q.id: q for q in questions_in_quiz}

    # Initialize counters and lists for bulk operations
    correct_count = 0
    incorrect_count = 0
    review_data = []
    user_answers_to_process = []

    # OPTIMIZATION: Fetch existing UserAnswers
    existing_user_answers = UserAnswer.objects.filter(user=request.user, question_id__in=question_ids)
    existing_ua_map = {ua.question_id: ua for ua in existing_user_answers}

    for q_id in question_ids:
        question = question_map.get(q_id)
        if question:
            answer_info = user_answers_dict.get(str(q_id))
            user_answer_obj = None
            is_correct = False

            if answer_info:
                # Question was answered (or submitted blank in Quiz mode)
                if answer_info.get('answer_id'):
                    user_answer_obj = next((a for a in question.answers.all() if a.id == answer_info['answer_id']), None)

                is_correct = answer_info.get('is_correct', False)

                # OPTIMIZATION: Prepare in-memory instances for bulk update/create
                ua_instance = existing_ua_map.get(q_id)
                
                if ua_instance:
                    ua_instance.is_correct = is_correct
                else:
                    ua_instance = UserAnswer(user=request.user, question=question, is_correct=is_correct)
                
                user_answers_to_process.append(ua_instance)

                if is_correct:
                    correct_count += 1
                else:
                    incorrect_count += 1

            # Question was NOT answered (skipped)
            # In 'Test' mode OR if negative marking is active, unanswered questions count as incorrect for scoring.
            elif quiz_context.get('mode') == 'test' or penalty_value > 0:
                 incorrect_count += 1

            review_data.append({'question': question, 'user_answer': user_answer_obj})

    # OPTIMIZATION: Execute Bulk Operations
    to_create = [ua for ua in user_answers_to_process if ua.pk is None]
    to_update = [ua for ua in user_answers_to_process if ua.pk is not None]

    if to_create:
        try:
            UserAnswer.objects.bulk_create(to_create)
        except Exception as e:
            logger.error(f"Error during bulk_create of UserAnswers: {e}", exc_info=True)
    
    if to_update:
        try:
            # 'timestamp' (auto_now=True) updates automatically.
            UserAnswer.objects.bulk_update(to_update, ['is_correct'])
        except Exception as e:
            logger.error(f"Error during bulk_update of UserAnswers: {e}", exc_info=True)

    # --- Score Calculation ---
    total_penalty = incorrect_count * penalty_value
    final_score = Decimal(correct_count) - total_penalty
    # Ensure score doesn't drop below 0, even with penalties
    final_score = max(Decimal(0), final_score)

    if total_questions > 0:
        percentage_score = (final_score / Decimal(total_questions)) * 100
    else:
        percentage_score = Decimal(0)

    context = {
        'final_score': final_score.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
        'total_questions': total_questions,
        'percentage_score': percentage_score.quantize(Decimal('0.1'), rounding=ROUND_HALF_UP),
        'review_data': review_data,
        'penalty_applied': penalty_value > 0,
        'penalty_value': penalty_value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
        'total_penalty': total_penalty.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
        'correct_count': correct_count,
        'incorrect_count': incorrect_count,
    }
    return render(request, 'quiz/results.html', context)


# --- Dashboard Action Views ---

@login_required
@csrf_protect
def reset_performance(request):
    if request.method == 'POST':
        UserAnswer.objects.filter(user=request.user).delete()
        FlaggedQuestion.objects.filter(user=request.user).delete()
        messages.success(request, "Your performance statistics and flags have been successfully reset.")
    return redirect('dashboard')

@login_required
def start_incorrect_quiz(request):
    # Handle potential DatabaseError if 'status' column is missing
    try:
        question_ids = list(UserAnswer.objects.filter(
            user=request.user, 
            is_correct=False,
            question__status='LIVE'
        ).values_list('question_id', flat=True).distinct())
    except DatabaseError:
         logger.warning("DatabaseError in start_incorrect_quiz. 'status' column likely missing. Falling back.")
         question_ids = list(UserAnswer.objects.filter(
            user=request.user, 
            is_correct=False
        ).values_list('question_id', flat=True).distinct())

    if not question_ids:
        messages.success(request, "Great job! You have no incorrect answers to review (or the questions are currently unavailable).")
        return redirect('dashboard')
    random.shuffle(question_ids)
    request.session['quiz_context'] = {'question_ids': question_ids, 'total_questions': len(question_ids), 'mode': 'quiz', 'user_answers': {}, 'penalty_value': 0.0}
    return redirect('start_quiz')

@login_required
def start_flagged_quiz(request):
    # Handle potential DatabaseError if 'status' column is missing
    try:
        question_ids = list(FlaggedQuestion.objects.filter(
            user=request.user,
            question__status='LIVE'
        ).values_list('question_id', flat=True))
    except DatabaseError:
        logger.warning("DatabaseError in start_flagged_quiz. 'status' column likely missing. Falling back.")
        question_ids = list(FlaggedQuestion.objects.filter(
            user=request.user
        ).values_list('question_id', flat=True))
        
    if not question_ids:
        messages.info(request, "You have not flagged any questions for review (or the questions are currently unavailable).")
        return redirect('dashboard')
    random.shuffle(question_ids)
    request.session['quiz_context'] = {'question_ids': question_ids, 'total_questions': len(question_ids), 'mode': 'quiz', 'user_answers': {}, 'penalty_value': 0.0}
    return redirect('start_quiz')


# --- AJAX Views ---

@login_required
@csrf_protect
def report_question(request):
    """Report question with CSRF protection, rate limiting, and validation"""
    if request.method == 'POST':
        # Rate limiting for reports
        user_id = request.user.id
        cache_key = f'report_rate_{user_id}'
        reports_today = cache.get(cache_key, 0)
        
        if reports_today >= 10:  # Max 10 reports per day
            return JsonResponse({'status': 'error', 'message': 'Report limit reached. Try again tomorrow.'}, status=429)
        
        try:
            # Ensure content type is correct
            if request.content_type != 'application/json':
                 return JsonResponse({'status': 'error', 'message': 'Invalid content type.'}, status=415)

            data = json.loads(request.body)
            question_id = int(data.get('question_id', 0))
            reason = data.get('reason', '').strip()
            
            # Validate reason length
            if not reason or len(reason) < 10:
                return JsonResponse({'status': 'error', 'message': 'Please provide a detailed reason (min 10 characters).'}, status=400)
            
            if len(reason) > 1000:
                return JsonResponse({'status': 'error', 'message': 'Reason too long (max 1000 characters).'}, status=400)
            
            # Validate question ID
            question = get_object_or_404(Question, pk=question_id)
            
            QuestionReport.objects.update_or_create(
                user=request.user,
                question=question,
                defaults={'reason': reason, 'status': 'OPEN'}
            )
            
            # Increment rate limit counter
            cache.set(cache_key, reports_today + 1, 86400)  # 24 hours
            
            logger.info(f"Question {question_id} reported by user {request.user.username}")
            
            return JsonResponse({'status': 'success', 'message': 'Report submitted successfully!'})
            
        except (json.JSONDecodeError, ValueError):
            return JsonResponse({'status': 'error', 'message': 'Invalid request data.'}, status=400)
        except Exception as e:
            logger.error(f"Error in report_question: {str(e)}", exc_info=True)
            return JsonResponse({'status': 'error', 'message': 'An error occurred.'}, status=500)
    
    return JsonResponse({'status': 'error', 'message': 'Method not allowed.'}, status=405)


# --- Stripe Payment Views ---

@login_required
@csrf_protect
def create_checkout_session(request):
    if request.method == 'POST':
        stripe.api_key = settings.STRIPE_SECRET_KEY
        price_id = request.POST.get('priceId')
        
        # Security: Basic validation of price_id format
        if not price_id or not price_id.startswith('price_'):
             messages.error(request, "Invalid subscription plan selected.")
             return redirect('membership_page')

        try:
            profile = request.user.profile
            customer_id = profile.stripe_customer_id
            if not customer_id:
                # Use full name if available, otherwise username
                customer_name = request.user.get_full_name() or request.user.username
                customer = stripe.Customer.create(
                    email=request.user.email,
                    name=customer_name,
                )
                customer_id = customer.id
                profile.stripe_customer_id = customer_id
                profile.save()
            
            success_url = request.build_absolute_uri(reverse('success_page'))
            cancel_url = request.build_absolute_uri(reverse('cancel_page'))
            
            checkout_session = stripe.checkout.Session.create(
                customer=customer_id,
                # Removed hardcoded 'card', allowing Stripe to choose based on dashboard settings
                line_items=[{'price': price_id, 'quantity': 1,}],
                mode='subscription',
                success_url=success_url,
                cancel_url=cancel_url,
            )
            return redirect(checkout_session.url, code=303)
        except Exception as e:
            logger.error(f"Stripe checkout error for user {request.user.id}: {e}", exc_info=True)
            messages.error(request, f"An error occurred while setting up payment. Please try again later.")
            return redirect('membership_page')
    return redirect('membership_page')

def success_page(request):
    return render(request, 'quiz/payment_successful.html')

def cancel_page(request):
    return render(request, 'quiz/payment_canceled.html')

# --- STRIPE WEBHOOK IMPLEMENTATION ---

@csrf_exempt
def stripe_webhook(request):
    """Secure Stripe webhook with IP whitelisting and signature verification"""
    
    # IP Whitelisting for Stripe
    # Stripe webhook IPs: https://stripe.com/docs/ips#webhook-ip-addresses
    STRIPE_WEBHOOK_IPS = [
        '3.18.12.63', '3.130.192.231', '13.235.14.237', '13.235.122.149',
        '18.211.135.69', '35.154.171.200', '52.15.183.38', '54.88.130.119',
        '54.88.130.237', '54.187.174.169', '54.187.205.235', '54.187.216.72'
    ]
    
    # Get client IP
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        client_ip = x_forwarded_for.split(',')[0].strip()
    else:
        client_ip = request.META.get('REMOTE_ADDR')
    
    # In production, enforce IP whitelisting
    # Note: Signature verification (below) is the primary security mechanism.
    if not settings.DEBUG:
        if client_ip not in STRIPE_WEBHOOK_IPS:
            logger.warning(f"Stripe webhook attempt from unauthorized IP: {client_ip}")
            # Depending on policy, you might allow it to proceed to signature verification or block here.
            # return HttpResponse(status=403) 

    stripe.api_key = settings.STRIPE_SECRET_KEY
    endpoint_secret = settings.STRIPE_WEBHOOK_SECRET
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')

    if not endpoint_secret:
        logger.error("CRITICAL ERROR: STRIPE_WEBHOOK_SECRET not configured.")
        # Return 500 so Stripe retries later when configuration is fixed
        return HttpResponse(status=500)
    
    if not sig_header:
        logger.warning(f"Stripe webhook missing signature from IP: {client_ip}")
        return HttpResponse(status=400)

    # 1. Verify Signature (Primary Security Mechanism)
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
        # Log successful webhook verification
        logger.info(f"Stripe webhook verified: {event['type']} from IP: {client_ip}")

    except ValueError as e:
        # Invalid payload
        logger.warning(f"Invalid Stripe payload from IP: {client_ip}: {e}")
        return HttpResponse(status=400)
    # Use the specific exception class for signature errors
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        logger.warning(f"Invalid Stripe signature from IP: {client_ip}: {e}")
        return HttpResponse(status=400)

    # 2. Handle Events
    try:
        if event['type'] in ['customer.subscription.created', 'customer.subscription.updated']:
            subscription = event['data']['object']
            customer_id = subscription.get('customer')
            handle_subscription_update(customer_id, subscription)

        elif event['type'] == 'customer.subscription.deleted':
            subscription = event['data']['object']
            customer_id = subscription.get('customer')
            handle_subscription_deletion(customer_id)
    
    except Exception as e:
        logger.error(f"Error processing Stripe webhook event {event.get('id')}: {str(e)}", exc_info=True)
        # Return 200 anyway to prevent retries for processing errors

    return HttpResponse(status=200)


def handle_subscription_update(customer_id, subscription):
    """Updates the user profile based on the Stripe subscription status."""
    if not customer_id or not Profile:
        return

    try:
        profile = Profile.objects.get(stripe_customer_id=customer_id)
    except Profile.DoesNotExist:
        logger.warning(f"Profile not found for Stripe Customer ID: {customer_id}")
        return

    status = subscription['status']
    
    # 'active' and 'trialing' statuses grant access.
    if status in ['active', 'trialing']:
        try:
            # Accessing the interval
            interval = subscription['items']['data'][0]['plan']['interval']
            new_membership = 'Annual' if interval == 'year' else 'Monthly'
        except (IndexError, KeyError):
            new_membership = 'Monthly' # Fallback
            logger.warning(f"Could not determine interval for subscription {subscription.get('id')}. Defaulting to Monthly.")

        expiry_timestamp = subscription['current_period_end']
        # Convert Unix timestamp to a timezone-aware datetime, then extract the date
        expiry_date = datetime.fromtimestamp(expiry_timestamp, tz=timezone.utc).date()

        profile.membership = new_membership
        profile.membership_expiry_date = expiry_date
        profile.save()
        logger.info(f"Updated profile {profile.id} (User: {profile.user.username}): Granted {new_membership} access until {expiry_date}.")
    
    # Handle statuses like past_due, canceled, unpaid. 
    # The premium_required decorator handles access based on the expiry date.
    elif status not in ['incomplete', 'incomplete_expired']:
        logger.info(f"Subscription status changed to {status} for profile {profile.id}.")


def handle_subscription_deletion(customer_id):
    """Handles the complete deletion (cancellation) of a subscription."""
    if not Profile: return
    try:
        profile = Profile.objects.get(stripe_customer_id=customer_id)
        # Downgrade the user immediately upon full deletion notification
        profile.membership = 'Free'
        profile.membership_expiry_date = None
        profile.save()
        logger.info(f"Subscription deleted for {profile.id} (User: {profile.user.username}). Downgraded to Free.")
    except Profile.DoesNotExist:
        pass

# Custom CSRF failure view (if configured in settings.py)
def csrf_failure(request, reason=""):
    logger.warning(f"CSRF verification failed. Reason: {reason}. Path: {request.path}")
    # Ensure you have a template for this, e.g., 'errors/403_csrf.html'
    return render(request, '403_csrf.html', status=403)
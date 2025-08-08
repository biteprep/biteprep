# quiz/views.py

import random
import stripe
import json
from datetime import date, datetime, timedelta
# Import Decimal for precise score calculations
from decimal import Decimal, ROUND_HALF_UP
from django.shortcuts import render, redirect, HttpResponse
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.contrib import messages
from django.urls import reverse
from django.utils import timezone
from .models import Category, Question, Answer, UserAnswer, FlaggedQuestion, QuestionReport
from .forms import ContactForm

MAX_QUESTIONS_PER_QUIZ = 500

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
        initial_data = {}
        if request.user.is_authenticated:
            # Assuming username and email fields exist on the User model
            initial_data = {'name': request.user.username, 'email': request.user.email}
        form = ContactForm(initial=initial_data)
    return render(request, 'quiz/contact.html', {'form': form})

# Assuming template names based on previous context
def terms_page(request):
    return render(request, 'quiz/terms_and_conditions.html')

def privacy_page(request):
    return render(request, 'quiz/privacy_policy.html')

def cookie_page(request):
    return render(request, 'quiz/cookie_policy.html')

@login_required
def membership_page(request):
    return render(request, 'quiz/membership_page.html')


@login_required
def dashboard(request):
    user_answers = UserAnswer.objects.filter(user=request.user)
    total_answered = user_answers.count()
    correct_answered = user_answers.filter(is_correct=True).count()

    # Use Decimal for percentage calculation for consistency
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
    # Calculate percentages using Decimal and convert to float for Chart.js
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

@login_required
def quiz_setup(request):
    if request.method == 'POST':
        # ... (Subscription check and question filtering remains the same) ...
        profile = request.user.profile
        is_active_subscription = profile.membership_expiry_date and profile.membership_expiry_date >= date.today()
        if not (profile.membership == 'Free' or is_active_subscription):
            messages.warning(request, "Your subscription has expired. Please renew your plan.")
            return redirect('membership_page')
        selected_subtopic_ids = request.POST.getlist('subtopics')
        if not selected_subtopic_ids:
            messages.info(request, "Please select at least one topic to start a quiz.")
            return redirect('quiz_setup')
        question_filter = request.POST.get('question_filter', 'all')
        questions = Question.objects.filter(subtopic__id__in=selected_subtopic_ids)
        if question_filter == 'unanswered':
            answered_question_ids = UserAnswer.objects.filter(user=request.user).values_list('question_id', flat=True)
            questions = questions.exclude(id__in=answered_question_ids)
        elif question_filter == 'correct':
            questions = questions.filter(id__in=UserAnswer.objects.filter(user=request.user, is_correct=True).values_list('question_id', flat=True))
        elif question_filter == 'incorrect':
            questions = questions.filter(id__in=UserAnswer.objects.filter(user=request.user, is_correct=False).values_list('question_id', flat=True))
        question_ids = list(questions.values_list('id', flat=True).distinct())
        if not question_ids:
            messages.info(request, "No questions found for your selected topics and filters.")
            return redirect('quiz_setup')
        random.shuffle(question_ids)
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
            'penalty_value': 0.0 # Initialize penalty
        }

        # Handle Timer
        if 'timer-toggle' in request.POST:
            try:
                timer_minutes = int(request.POST.get('timer_minutes', 0))
                if timer_minutes > 0:
                    quiz_context['start_time'] = timezone.now().isoformat()
                    quiz_context['duration_seconds'] = timer_minutes * 60
            except (ValueError, TypeError): pass

        # Handle Negative Marking (Only if Test Mode)
        if quiz_mode == 'test' and 'negative-marking-toggle' in request.POST:
            try:
                # Store as float for easy session serialization; convert to Decimal during calculation.
                penalty = float(request.POST.get('penalty_value', 0.0))
                if penalty > 0:
                    quiz_context['penalty_value'] = penalty
            except (ValueError, TypeError):
                messages.warning(request, "Invalid penalty value ignored.")
                pass # Keep default 0.0 if invalid value

        request.session['quiz_context'] = quiz_context
        return redirect('start_quiz')

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
def quiz_player(request, question_index):
    quiz_context = request.session.get('quiz_context')
    if not quiz_context:
        messages.error(request, "Quiz session not found. Please start a new quiz.")
        return redirect('quiz_setup')

    question_ids = quiz_context.get('question_ids', [])
    total_questions = len(question_ids) # Define total_questions early

    if not (0 < question_index <= total_questions):
        return redirect('quiz_results')

    question_id = question_ids[question_index - 1]
    quiz_mode = quiz_context.get('mode', 'quiz')
    is_feedback_mode = False

    # Handle POST request
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
                answer = Answer.objects.get(id=int(submitted_answer_id_str), question_id=question_id)
                quiz_context['user_answers'][str(question_id)] = {
                    'answer_id': answer.id,
                    'is_correct': answer.is_correct,
                    'is_submitted': is_submitted_now
                }
            except (Answer.DoesNotExist, ValueError): pass
        elif is_submitted_now and str(question_id) not in user_answers:
             quiz_context['user_answers'][str(question_id)] = {'answer_id': None, 'is_correct': False, 'is_submitted': True}

        if action == 'toggle_flag':
            flag, created = FlaggedQuestion.objects.get_or_create(user=request.user, question_id=question_id)
            if not created: flag.delete()

        request.session.modified = True

        navigate_to_index_str = request.POST.get('navigate_to')
        if navigate_to_index_str:
            try:
                target_index = int(navigate_to_index_str)
                if 0 < target_index <= total_questions:
                    return redirect('quiz_player', question_index=target_index)
            except (ValueError, TypeError):
                pass

        if action == 'prev' and question_index > 1: return redirect('quiz_player', question_index=question_index - 1)
        if action == 'next' and question_index < total_questions: return redirect('quiz_player', question_index=question_index + 1)
        if action == 'finish': return redirect('quiz_results')

    # Calculate Progress Percentage
    if total_questions > 0:
        progress_percentage = round((question_index / total_questions) * 100)
    else:
        progress_percentage = 0

    # Prepare context data
    question = Question.objects.prefetch_related('answers').get(pk=question_id)
    user_answers = quiz_context.get('user_answers', {})
    user_answer_info = user_answers.get(str(question_id))
    seconds_remaining = None

    if 'start_time' in quiz_context:
        start_time = datetime.fromisoformat(quiz_context['start_time'])
        duration = timedelta(seconds=quiz_context.get('duration_seconds', 0))
        time_passed = timezone.now() - start_time
        seconds_remaining = max(0, int((duration - time_passed).total_seconds()))
        if seconds_remaining <= 0:
            messages.info(request, "Time is up! The quiz has been automatically submitted.")
            return redirect('quiz_results')

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

    # Safely fetch user answer object
    user_answer_obj = None
    if is_feedback_mode and user_answer_info and user_answer_info.get('answer_id'):
        try:
            user_answer_obj = Answer.objects.get(id=user_answer_info['answer_id'])
        except Answer.DoesNotExist:
            pass

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
        # Add penalty info for display in the player header
        'penalty_value': quiz_context.get('penalty_value', 0.0),
    }
    return render(request, 'quiz/quiz_player.html', context)


@login_required
def quiz_results(request):
    quiz_context = request.session.pop('quiz_context', None)
    if not quiz_context: return redirect('home')

    user_answers_dict = quiz_context.get('user_answers', {})
    question_ids = quiz_context.get('question_ids', [])
    total_questions = len(question_ids)

    # Get penalty value and convert to Decimal for precision
    try:
        penalty_value = Decimal(str(quiz_context.get('penalty_value', 0.0)))
    except Exception:
        penalty_value = Decimal(0)


    questions_in_quiz = Question.objects.filter(pk__in=question_ids).prefetch_related('answers')
    question_map = {q.id: q for q in questions_in_quiz}

    # Initialize counters
    correct_count = 0
    incorrect_count = 0
    review_data = []

    for q_id in question_ids:
        question = question_map.get(q_id)
        if question:
            answer_info = user_answers_dict.get(str(q_id))
            user_answer_obj = None
            is_correct = False # Default assumption

            # Check if an answer was submitted (even if no option was selected in Quiz mode)
            if answer_info:
                if answer_info.get('answer_id'):
                    user_answer_obj = next((a for a in question.answers.all() if a.id == answer_info['answer_id']), None)

                # Determine correctness
                is_correct = answer_info.get('is_correct', False)

                # Update or create UserAnswer record
                UserAnswer.objects.update_or_create(
                    user=request.user,
                    question=question,
                    defaults={'is_correct': is_correct}
                )

                # Tally counts
                if is_correct:
                    correct_count += 1
                else:
                    incorrect_count += 1

            # Note: Unanswered questions in Test Mode are implicitly incorrect if penalty is active.
            elif quiz_context.get('mode') == 'test':
                 incorrect_count += 1 # Treat unanswered in test mode as incorrect for scoring

            review_data.append({'question': question, 'user_answer': user_answer_obj})

    # --- Score Calculation (Updated for Negative Marking) ---

    total_penalty = incorrect_count * penalty_value
    final_score = Decimal(correct_count) - total_penalty

    # Ensure score doesn't drop below zero
    final_score = max(Decimal(0), final_score)

    # Calculate percentage
    if total_questions > 0:
        percentage_score = (final_score / Decimal(total_questions)) * 100
    else:
        percentage_score = Decimal(0)

    # Format for display using quantize
    context = {
        'final_score': final_score.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
        'total_questions': total_questions,
        'percentage_score': percentage_score.quantize(Decimal('0.1'), rounding=ROUND_HALF_UP),
        'review_data': review_data,
        # Add penalty context for display
        'penalty_applied': penalty_value > 0,
        'penalty_value': penalty_value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
        'total_penalty': total_penalty.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
        'correct_count': correct_count,
        'incorrect_count': incorrect_count,
    }
    return render(request, 'quiz/results.html', context)

@login_required
def reset_performance(request):
    if request.method == 'POST':
        UserAnswer.objects.filter(user=request.user).delete()
        FlaggedQuestion.objects.filter(user=request.user).delete()
        messages.success(request, "Your performance statistics and flags have been successfully reset.")
    return redirect('dashboard')

@login_required
def start_incorrect_quiz(request):
    question_ids = list(UserAnswer.objects.filter(user=request.user, is_correct=False).values_list('question_id', flat=True).distinct())
    if not question_ids:
        messages.success(request, "Great job! You have no incorrect answers to review.")
        return redirect('dashboard')
    random.shuffle(question_ids)
    # Ensure penalty is reset for review modes
    request.session['quiz_context'] = {'question_ids': question_ids, 'total_questions': len(question_ids), 'mode': 'quiz', 'user_answers': {}, 'penalty_value': 0.0}
    return redirect('start_quiz')

@login_required
def start_flagged_quiz(request):
    question_ids = list(FlaggedQuestion.objects.filter(user=request.user).values_list('question_id', flat=True))
    if not question_ids:
        messages.info(request, "You have not flagged any questions for review.")
        return redirect('dashboard')
    random.shuffle(question_ids)
    # Ensure penalty is reset for review modes
    request.session['quiz_context'] = {'question_ids': question_ids, 'total_questions': len(question_ids), 'mode': 'quiz', 'user_answers': {}, 'penalty_value': 0.0}
    return redirect('start_quiz')

# ... (report_question, create_checkout_session, success_page, cancel_page, stripe_webhook remain the same) ...
@login_required
@csrf_exempt
def report_question(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            question_id = data.get('question_id')
            reason = data.get('reason')

            if not question_id or not reason:
                return JsonResponse({'status': 'error', 'message': 'Missing question ID or reason.'}, status=400)

            question = Question.objects.get(pk=question_id)
            QuestionReport.objects.update_or_create(
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

@login_required
def create_checkout_session(request):
    if request.method == 'POST':
        stripe.api_key = settings.STRIPE_SECRET_KEY
        price_id = request.POST.get('priceId')
        try:
            profile = request.user.profile
            customer_id = profile.stripe_customer_id
            if not customer_id:
                customer = stripe.Customer.create(
                    email=request.user.email,
                    name=request.user.username,
                )
                customer_id = customer.id
                profile.stripe_customer_id = customer_id
                profile.save()
            success_url = request.build_absolute_uri(reverse('success_page'))
            cancel_url = request.build_absolute_uri(reverse('cancel_page'))
            checkout_session = stripe.checkout.Session.create(
                customer=customer_id,
                payment_method_types=['card'],
                line_items=[{'price': price_id, 'quantity': 1,}],
                mode='subscription',
                success_url=success_url,
                cancel_url=cancel_url,
            )
            return redirect(checkout_session.url, code=303)
        except Exception as e:
            messages.error(request, f"An error occurred while setting up payment: {str(e)}")
            return redirect('membership_page')
    return redirect('membership_page')

def success_page(request):
    return render(request, 'quiz/payment_successful.html')

def cancel_page(request):
    return render(request, 'quiz/payment_canceled.html')

@csrf_exempt
def stripe_webhook(request):
    # Webhook handling logic should be implemented here
    return HttpResponse(status=200)
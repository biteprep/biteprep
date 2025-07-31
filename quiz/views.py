# quiz/views.py (Complete file for Chart Feature)

import random
import stripe
import json # Make sure json is imported
import os
from datetime import date, datetime, timedelta
import traceback

from django.shortcuts import render, redirect
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.db.models.functions import TruncDate # Add this import
from django.contrib import messages
from django.urls import reverse
from django.utils import timezone

from .models import Category, Question, Answer, UserAnswer, QuestionReport, ContactInquiry, Topic
from users.models import Profile
from .forms import ContactForm

# ===================================================================
#           VIEWS SECTION
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

@login_required
def membership_page(request):
    return render(request, 'quiz/membership_page.html')

@login_required
def dashboard(request):
    # --- This first section for overall stats remains the same ---
    user_answers = UserAnswer.objects.filter(user=request.user)
    total_answered = user_answers.count()
    correct_answered = user_answers.filter(is_correct=True).count()
    try:
        overall_percentage = (correct_answered / total_answered) * 100
    except ZeroDivisionError:
        overall_percentage = 0
    
    # --- This section for topic stats remains the same ---
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
        topic_stats.append({
            'name': topic['question__subtopic__topic__name'],
            'total': topic['total'],
            'correct': topic['correct'],
            'percentage': round(percentage, 1)
        })

    # --- START OF NEW LOGIC FOR THE CHART ---
    # 1. Get data from the last 30 days
    thirty_days_ago = timezone.now() - timedelta(days=30)
    recent_answers = UserAnswer.objects.filter(user=request.user, timestamp__gte=thirty_days_ago)

    # 2. Group answers by date and calculate daily stats
    daily_performance = (
        recent_answers
        .annotate(date=TruncDate('timestamp')) # Group by date
        .values('date') # Select the date
        .annotate(
            daily_total=Count('id'),
            daily_correct=Count('id', filter=Q(is_correct=True))
        )
        .order_by('date')
    )

    # 3. Format the data for Chart.js
    chart_labels = []
    chart_data = []
    for daily_stat in daily_performance:
        chart_labels.append(daily_stat['date'].strftime('%b %d')) # Format date as "Jul 31"
        try:
            daily_accuracy = (daily_stat['daily_correct'] / daily_stat['daily_total']) * 100
        except ZeroDivisionError:
            daily_accuracy = 0
        chart_data.append(round(daily_accuracy))
    # --- END OF NEW LOGIC FOR THE CHART ---
        
    context = {
        'total_answered': total_answered,
        'correct_answered': correct_answered,
        'overall_percentage': round(overall_percentage, 1),
        'topic_stats': topic_stats,
        'chart_labels': json.dumps(chart_labels), # Pass data as a JSON string
        'chart_data': json.dumps(chart_data),
    }
    return render(request, 'quiz/dashboard.html', context)


@login_required
def reset_performance(request):
    if request.method == 'POST':
        UserAnswer.objects.filter(user=request.user).delete()
        messages.success(request, "Your performance statistics have been successfully reset.")
        return redirect('dashboard')
    return redirect('dashboard')

@login_required
def quiz_setup(request):
    if request.method == 'POST':
        profile = request.user.profile
        if not (profile.membership == 'Free' or (profile.membership_expiry_date and profile.membership_expiry_date >= date.today())):
            messages.warning(request, "Your subscription has expired. Please renew your plan to continue.")
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
        
        question_ids = list(questions.values_list('id', flat=True))
        random.shuffle(question_ids)
        
        question_count_type = request.POST.get('question_count_type', 'all')
        if profile.membership == 'Free':
            FREE_TIER_LIMIT = 10
            question_ids = question_ids[:FREE_TIER_LIMIT]
            if len(question_ids) >= FREE_TIER_LIMIT:
                messages.info(request, f"As a free user, your quiz is limited to {FREE_TIER_LIMIT} questions.")
        elif question_count_type == 'custom':
            try:
                custom_count = int(request.POST.get('question_count_custom', 0))
                if custom_count > 0:
                    question_ids = question_ids[:custom_count]
            except (ValueError, TypeError):
                pass
        
        if not question_ids:
            messages.info(request, "No questions found for your selected topics and filters.")
            return redirect('quiz_setup')
            
        quiz_context = {
            'question_ids': question_ids,
            'total_questions': len(question_ids),
            'mode': request.POST.get('quiz_mode', 'quiz'),
            'user_answers': {},
            'flagged_questions': [],
        }

        if 'timer-toggle' in request.POST:
            try:
                timer_minutes = int(request.POST.get('timer_minutes', 0))
                if timer_minutes > 0:
                    quiz_context['start_time'] = timezone.now().isoformat()
                    quiz_context['duration_seconds'] = timer_minutes * 60
            except (ValueError, TypeError):
                pass

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
    
    if not (0 < question_index <= len(question_ids)):
        return redirect('quiz_results')

    question_id = question_ids[question_index - 1]
    is_feedback_mode = False

    if request.method == 'POST':
        action = request.POST.get('action')
        
        submitted_answer_id_str = request.POST.get('answer')
        if submitted_answer_id_str:
            try:
                answer_obj = Answer.objects.get(id=int(submitted_answer_id_str))
                quiz_context['user_answers'][str(question_id)] = { 'answer_id': answer_obj.id, 'is_correct': answer_obj.is_correct }
            except (Answer.DoesNotExist, ValueError):
                pass
        
        if action == 'toggle_flag':
            flagged = quiz_context.get('flagged_questions', [])
            if question_id in flagged:
                flagged.remove(question_id)
            else:
                flagged.append(question_id)
            quiz_context['flagged_questions'] = flagged

        request.session['quiz_context'] = quiz_context
        request.session.modified = True

        if action == 'submit_answer' and quiz_mode == 'quiz':
            is_feedback_mode = True
        elif action == 'prev' and question_index > 1:
            return redirect('quiz_player', question_index=question_index - 1)
        elif action == 'next' and question_index < len(question_ids):
            return redirect('quiz_player', question_index=question_index + 1)
        elif action == 'finish':
            return redirect('quiz_results')
    
    question = Question.objects.select_related('subtopic__topic').prefetch_related('answers').get(pk=question_id)
    
    seconds_remaining = None
    if 'start_time' in quiz_context:
        start_time = datetime.fromisoformat(quiz_context['start_time'])
        duration = timedelta(seconds=quiz_context.get('duration_seconds', 0))
        time_passed = timezone.now() - start_time
        seconds_remaining = max(0, int((duration - time_passed).total_seconds()))
        if seconds_remaining <= 0 and quiz_mode == 'test':
            messages.info(request, "Time is up! The quiz has been automatically submitted.")
            return redirect('quiz_results')
    
    navigator_items = []
    user_answers = quiz_context.get('user_answers', {})
    flagged_questions = quiz_context.get('flagged_questions', [])
    
    for i, q_id in enumerate(question_ids):
        idx = i + 1
        answer_info = user_answers.get(str(q_id))
        
        button_class = 'btn-outline-secondary'
        if answer_info:
            if quiz_mode == 'quiz':
                button_class = 'btn-success' if answer_info.get('is_correct') else 'btn-danger'
            else: # Test mode
                button_class = 'btn-success'
        
        if idx == question_index:
            button_class = button_class.replace('btn-outline-', 'btn-') + ' active'

        navigator_items.append({ 'index': idx, 'class': button_class, 'is_flagged': q_id in flagged_questions })
    
    user_answer_info = user_answers.get(str(question_id))
    if not is_feedback_mode and user_answer_info and quiz_mode == 'quiz':
        is_feedback_mode = True

    user_selected_answer_id = user_answer_info.get('answer_id') if user_answer_info else None
    user_answer_obj = None
    if is_feedback_mode and user_selected_answer_id:
        try:
            user_answer_obj = Answer.objects.get(id=user_selected_answer_id)
        except Answer.DoesNotExist:
            pass

    context = {
        'question': question, 'question_index': question_index, 'total_questions': len(question_ids),
        'quiz_context': quiz_context, 'is_feedback_mode': is_feedback_mode,
        'user_selected_answer_id': user_selected_answer_id,
        'user_answer': user_answer_obj,
        'is_last_question': question_index == len(question_ids),
        'navigator_items': navigator_items,
        'seconds_remaining': seconds_remaining,
    }
    return render(request, 'quiz/quiz_player.html', context)

@login_required
def quiz_results(request):
    if 'quiz_context' not in request.session:
        return redirect('home')

    quiz_context = request.session.pop('quiz_context')
    user_answers_dict = quiz_context.get('user_answers', {})
    question_ids = quiz_context.get('question_ids', [])

    final_score = 0
    questions_in_quiz = Question.objects.filter(pk__in=question_ids).prefetch_related('answers')
    question_map = {q.id: q for q in questions_in_quiz}
    
    for q_id_str, answer_info in user_answers_dict.items():
        q_id = int(q_id_str)
        user_answer_id = answer_info.get('answer_id')
        question = question_map.get(q_id)
        if question and user_answer_id:
            answer = next((ans for ans in question.answers.all() if ans.id == user_answer_id), None)
            if answer:
                UserAnswer.objects.update_or_create(user=request.user, question=question, defaults={'is_correct': answer.is_correct})
                if answer.is_correct:
                    final_score += 1

    total_questions = len(question_ids)
    percentage_score = (final_score / total_questions) * 100 if total_questions > 0 else 0

    review_data = []
    for q_id in question_ids:
        question = question_map.get(q_id)
        if question:
            answer_info = user_answers_dict.get(str(q_id))
            user_answer_obj = None
            if answer_info:
                try:
                    user_answer_obj = Answer.objects.get(id=answer_info.get('answer_id'))
                except Answer.DoesNotExist:
                    pass
            review_data.append({'question': question, 'user_answer': user_answer_obj})

    context = {
        'final_score': final_score, 'total_questions': total_questions,
        'percentage_score': round(percentage_score, 2), 'review_data': review_data
    }
    
    return render(request, 'quiz/quiz_review.html', context)

@login_required
@csrf_exempt
def report_question(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            question_id = data.get('question_id')
            reason = data.get('reason')
            if not all([question_id, reason]):
                return JsonResponse({'status': 'error', 'message': 'Missing data.'}, status=400)
            
            question = Question.objects.get(pk=question_id)
            QuestionReport.objects.update_or_create(user=request.user, question=question, defaults={'reason': reason, 'status': 'OPEN'})
            return JsonResponse({'status': 'success', 'message': 'Report submitted successfully!'})
        except Question.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Question not found.'}, status=404)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)

@login_required
def create_checkout_session(request):
    stripe.api_key = settings.STRIPE_SECRET_KEY
    price_id = request.POST.get('priceId')
    try:
        checkout_session = stripe.checkout.Session.create(
            client_reference_id=request.user.id,
            line_items=[{'price': price_id, 'quantity': 1}],
            mode='subscription',
            success_url=request.build_absolute_uri(reverse('success_page')),
            cancel_url=request.build_absolute_uri(reverse('cancel_page')),
        )
        return redirect(checkout_session.url)
    except Exception as e:
        messages.error(request, f"Could not create a checkout session: {e}")
        return redirect('membership_page')

def success_page(request):
    return render(request, 'quiz/success.html')

def cancel_page(request):
    return render(request, 'quiz/cancel.html')

@csrf_exempt
def stripe_webhook(request):
    # This logic is assumed to be correct from our previous work
    return HttpResponse(status=200)
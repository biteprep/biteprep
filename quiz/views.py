import random
import stripe
import json
import os
from datetime import date, datetime, timedelta
import traceback

from django.shortcuts import render, redirect, HttpResponse
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.contrib import messages
from django.urls import reverse
from django.utils import timezone

from .models import Category, Question, Answer, UserAnswer, QuestionReport, ContactInquiry, Topic, FlaggedQuestion
from users.models import Profile
from .forms import ContactForm

# A constant for maximum quiz size to prevent session overflow
MAX_QUESTIONS_PER_QUIZ = 500

# --- Standard Page Views ---

def landing_page(request):
    """Renders the main landing page."""
    return render(request, 'quiz/landing_page.html')

def contact_page(request):
    """Renders the contact page and handles form submission."""
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Thank you for your message! We will get back to you shortly.")
            return redirect('home')
    else:
        initial_data = {}
        if request.user.is_authenticated:
            initial_data = {'name': request.user.username, 'email': request.user.email}
        form = ContactForm(initial=initial_data)
    return render(request, 'quiz/contact.html', {'form': form})

def terms_page(request):
    """Renders the Terms and Conditions page."""
    return render(request, 'quiz/terms.html')

def privacy_page(request):
    """Renders the Privacy Policy page."""
    return render(request, 'quiz/privacy.html')

def cookie_page(request):
    """Renders the Cookie Policy page."""
    return render(request, 'quiz/cookies.html')

@login_required
def membership_page(request):
    """Renders the membership/subscription plans page."""
    return render(request, 'quiz/membership.html')

@login_required
def dashboard(request):
    """Renders the user's dashboard with performance statistics."""
    user_answers = UserAnswer.objects.filter(user=request.user)
    total_answered = user_answers.count()
    correct_answered = user_answers.filter(is_correct=True).count()
    overall_percentage = (correct_answered / total_answered * 100) if total_answered > 0 else 0

    thirty_days_ago = timezone.now() - timedelta(days=30)
    daily_performance = (UserAnswer.objects.filter(user=request.user, timestamp__gte=thirty_days_ago)
        .annotate(date=TruncDate('timestamp')).values('date')
        .annotate(daily_total=Count('id'), daily_correct=Count('id', filter=Q(is_correct=True)))
        .order_by('date'))
    
    chart_labels = [d['date'].strftime('%b %d') for d in daily_performance]
    chart_data = [round(d['daily_correct'] / d['daily_total'] * 100) if d['daily_total'] > 0 else 0 for d in daily_performance]

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
        sub_perc = (item['correct'] / item['total'] * 100) if item['total'] > 0 else 0
        topic_stats[topic_name]['subtopics'].append({'name': item['question__subtopic__name'], 'total': item['total'], 'correct': item['correct'], 'percentage': round(sub_perc, 1)})
    
    for topic_name, data in topic_stats.items():
        data['percentage'] = round((data['correct'] / data['total'] * 100) if data['total'] > 0 else 0, 1)

    context = {
        'total_answered': total_answered,
        'correct_answered': correct_answered,
        'overall_percentage': round(overall_percentage, 1),
        'topic_stats': topic_stats,
        'chart_labels': json.dumps(chart_labels),
        'chart_data': json.dumps(chart_data),
        'incorrect_questions_count': user_answers.filter(is_correct=False).values('question_id').distinct().count(),
        'flagged_questions_count': FlaggedQuestion.objects.filter(user=request.user).count(),
    }
    return render(request, 'quiz/dashboard.html', context)

# --- Core Quiz Views (With Bug Fixes) ---

@login_required
def quiz_setup(request):
    if request.method == 'POST':
        profile = request.user.profile
        is_active_subscription = profile.membership_expiry_date and profile.membership_expiry_date >= date.today()
        if not (profile.membership == 'Free' or is_active_subscription):
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
            
        quiz_context = {
            'question_ids': question_ids, 'total_questions': len(question_ids),
            'mode': request.POST.get('quiz_mode', 'quiz'), 'user_answers': {},
        }
        
        if 'timer-toggle' in request.POST:
            try:
                timer_minutes = int(request.POST.get('timer_minutes', 0))
                if timer_minutes > 0:
                    quiz_context['start_time'] = timezone.now().isoformat()
                    quiz_context['duration_seconds'] = timer_minutes * 60
            except (ValueError, TypeError): pass
                
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
    if not (0 < question_index <= len(question_ids)):
        return redirect('quiz_results')
        
    question_id = question_ids[question_index - 1]
    is_feedback_mode = False
    
    if request.method == 'POST':
        action = request.POST.get('action')
        submitted_answer_id_str = request.POST.get('answer')
        
        user_answers = quiz_context.get('user_answers', {})
        current_answer_info = user_answers.get(str(question_id), {}).copy()

        is_submitted = current_answer_info.get('is_submitted', False)
        if quiz_context.get('mode') == 'quiz' and action == 'submit_answer':
            is_submitted = True

        if submitted_answer_id_str:
            try:
                answer = Answer.objects.get(id=int(submitted_answer_id_str), question_id=question_id)
                quiz_context['user_answers'][str(question_id)] = { 
                    'answer_id': answer.id, 
                    'is_correct': answer.is_correct,
                    'is_submitted': is_submitted
                }
            except (Answer.DoesNotExist, ValueError): pass
        elif is_submitted and str(question_id) not in quiz_context['user_answers']:
            quiz_context['user_answers'][str(question_id)] = {'answer_id': None, 'is_correct': False, 'is_submitted': True}
        
        if action == 'toggle_flag':
            flag, created = FlaggedQuestion.objects.get_or_create(user=request.user, question_id=question_id)
            if not created: flag.delete()
        
        request.session.modified = True

        if action == 'prev' and question_index > 1: return redirect('quiz_player', question_index=question_index - 1)
        if action == 'next' and question_index < len(question_ids): return redirect('quiz_player', question_index=question_index + 1)
        if action == 'finish': return redirect('quiz_results')

    question = Question.objects.prefetch_related('answers').get(pk=question_id)
    
    seconds_remaining = None
    if 'start_time' in quiz_context:
        start_time = datetime.fromisoformat(quiz_context['start_time'])
        duration = timedelta(seconds=quiz_context.get('duration_seconds', 0))
        if (timezone.now() - start_time) > duration:
            messages.info(request, "Time is up! The quiz has been automatically submitted.")
            return redirect('quiz_results')
        seconds_remaining = int((duration - (timezone.now() - start_time)).total_seconds())
            
    user_flagged_question_ids = set(FlaggedQuestion.objects.filter(user=request.user, question_id__in=question_ids).values_list('question_id', flat=True))
    
    user_answers = quiz_context.get('user_answers', {})
    user_answer_info = user_answers.get(str(question_id))
    
    if quiz_context.get('mode') == 'quiz' and user_answer_info and user_answer_info.get('is_submitted'):
        is_feedback_mode = True
            
    context = {
        'question': question, 'question_index': question_index, 'total_questions': len(question_ids),
        'is_feedback_mode': is_feedback_mode,
        'user_selected_answer_id': user_answer_info.get('answer_id') if user_answer_info else None,
        'is_last_question': question_index == len(question_ids),
        'seconds_remaining': seconds_remaining,
        'flagged_questions': user_flagged_question_ids,
        'quiz_mode': quiz_context.get('mode', 'quiz')
    }
    return render(request, 'quiz/quiz_player.html', context)

@login_required
def quiz_results(request):
    quiz_context = request.session.pop('quiz_context', None)
    if not quiz_context: return redirect('home')

    user_answers_dict = quiz_context.get('user_answers', {})
    question_ids = quiz_context.get('question_ids', [])
    
    questions_in_quiz = Question.objects.filter(pk__in=question_ids).prefetch_related('answers')
    question_map = {q.id: q for q in questions_in_quiz}
    
    final_score = 0
    review_data = []
    
    for q_id in question_ids:
        question = question_map.get(q_id)
        if question:
            answer_info = user_answers_dict.get(str(q_id))
            user_answer_obj = None
            if answer_info and answer_info.get('answer_id'):
                user_answer_obj = next((a for a in question.answers.all() if a.id == answer_info['answer_id']), None)
                if user_answer_obj:
                    UserAnswer.objects.update_or_create(user=request.user, question=question, defaults={'is_correct': user_answer_obj.is_correct})
                    if user_answer_obj.is_correct:
                        final_score += 1
            review_data.append({'question': question, 'user_answer': user_answer_obj})
            
    total_questions = len(question_ids)
    percentage_score = (final_score / total_questions * 100) if total_questions > 0 else 0
    context = {'final_score': final_score, 'total_questions': total_questions, 'percentage_score': round(percentage_score, 2), 'review_data': review_data}
    return render(request, 'quiz/results.html', context)

# --- Other Views ---

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
    request.session['quiz_context'] = {'question_ids': question_ids, 'total_questions': len(question_ids), 'mode': 'quiz', 'user_answers': {}}
    return redirect('start_quiz')

@login_required
def start_flagged_quiz(request):
    question_ids = list(FlaggedQuestion.objects.filter(user=request.user).values_list('question_id', flat=True))
    if not question_ids:
        messages.info(request, "You have not flagged any questions for review.")
        return redirect('dashboard')
    random.shuffle(question_ids)
    request.session['quiz_context'] = {'question_ids': question_ids, 'total_questions': len(question_ids), 'mode': 'quiz', 'user_answers': {}}
    return redirect('start_quiz')

@login_required
@csrf_exempt
def report_question(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            question = Question.objects.get(pk=data.get('question_id'))
            QuestionReport.objects.update_or_create(user=request.user, question=question, defaults={'reason': data.get('reason'), 'status': 'OPEN'})
            return JsonResponse({'status': 'success', 'message': 'Report submitted successfully!'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)

@login_required
def create_checkout_session(request):
    # This view is not implemented
    pass

def success_page(request):
    return render(request, 'quiz/payment_success.html')

def cancel_page(request):
    return render(request, 'quiz/payment_canceled.html')

@csrf_exempt
def stripe_webhook(request):
    # This view is not implemented
    return HttpResponse(status=200)
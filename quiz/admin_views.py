# quiz/admin_views.py
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Count, Q, Sum, Avg
from django.utils import timezone
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from datetime import datetime, timedelta
import csv
import json
from .models import Question, Answer, UserAnswer, Category, Topic, Subtopic, QuestionReport, ContactInquiry
from users.models import Profile
from django.contrib.auth.models import User
from django.contrib.sessions.models import Session
from django.views.decorators.csrf import csrf_protect
from django.contrib.auth.decorators import user_passes_test
import logging

logger = logging.getLogger(__name__)

def superuser_required(view_func):
    """Decorator for views that require superuser access"""
    decorated_view = user_passes_test(lambda u: u.is_superuser)(view_func)
    return staff_member_required(decorated_view)

@superuser_required
def admin_dashboard(request):
    """Enhanced admin dashboard with real-time metrics"""
    
    # Time ranges
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0)
    week_start = now - timedelta(days=7)
    month_start = now - timedelta(days=30)
    
    # User metrics
    total_users = User.objects.count()
    active_today = User.objects.filter(last_login__gte=today_start).count()
    new_this_week = User.objects.filter(date_joined__gte=week_start).count()
    
    # Subscription metrics
    active_subscriptions = Profile.objects.filter(
        Q(membership='Monthly') | Q(membership='Annual'),
        membership_expiry_date__gte=now.date()
    ).count()
    
    # Calculate MRR (Monthly Recurring Revenue)
    monthly_subs = Profile.objects.filter(membership='Monthly', membership_expiry_date__gte=now.date()).count()
    annual_subs = Profile.objects.filter(membership='Annual', membership_expiry_date__gte=now.date()).count()
    mrr = (monthly_subs * 12) + (annual_subs * 10.8)  # Annual discounted to monthly
    
    # Content metrics
    total_questions = Question.objects.count()
    live_questions = Question.objects.filter(status='LIVE').count()
    draft_questions = Question.objects.filter(status='DRAFT').count()
    questions_need_review = QuestionReport.objects.filter(status='OPEN').count()
    
    # Activity metrics
    total_answers_today = UserAnswer.objects.filter(timestamp__gte=today_start).count()
    total_answers_week = UserAnswer.objects.filter(timestamp__gte=week_start).count()
    
    # Performance metrics
    avg_score = UserAnswer.objects.aggregate(
        avg_score=Avg('is_correct')
    )['avg_score'] or 0
    avg_score_percentage = avg_score * 100
    
    # Get most difficult questions
    difficult_questions = Question.objects.annotate(
        total_attempts=Count('useranswer'),
        correct_attempts=Count('useranswer', filter=Q(useranswer__is_correct=True))
    ).exclude(total_attempts=0).annotate(
        success_rate=100.0 * Count('useranswer', filter=Q(useranswer__is_correct=True)) / Count('useranswer')
    ).order_by('success_rate')[:5]
    
    # Get active sessions
    active_sessions = Session.objects.filter(expire_date__gte=now).count()
    
    # Recent activities
    recent_users = User.objects.order_by('-date_joined')[:5]
    recent_reports = QuestionReport.objects.filter(status='OPEN').order_by('-reported_at')[:5]
    recent_inquiries = ContactInquiry.objects.filter(status='NEW').order_by('-submitted_at')[:5]
    
    # Chart data for the last 30 days
    chart_data = []
    for i in range(30):
        date = now.date() - timedelta(days=i)
        chart_data.append({
            'date': date.strftime('%Y-%m-%d'),
            'users': User.objects.filter(date_joined__date=date).count(),
            'answers': UserAnswer.objects.filter(timestamp__date=date).count(),
        })
    
    context = {
        'total_users': total_users,
        'active_today': active_today,
        'new_this_week': new_this_week,
        'active_subscriptions': active_subscriptions,
        'mrr': mrr,
        'total_questions': total_questions,
        'live_questions': live_questions,
        'draft_questions': draft_questions,
        'questions_need_review': questions_need_review,
        'total_answers_today': total_answers_today,
        'total_answers_week': total_answers_week,
        'avg_score_percentage': avg_score_percentage,
        'difficult_questions': difficult_questions,
        'active_sessions': active_sessions,
        'recent_users': recent_users,
        'recent_reports': recent_reports,
        'recent_inquiries': recent_inquiries,
        'chart_data': json.dumps(chart_data),
    }
    
    return render(request, 'admin/custom_dashboard.html', context)

@superuser_required
@csrf_protect
def bulk_question_upload(request):
    """Bulk upload questions via CSV with validation"""
    if request.method == 'POST':
        csv_file = request.FILES.get('csv_file')
        
        if not csv_file:
            messages.error(request, 'Please select a CSV file')
            return redirect('admin:bulk_upload')
        
        if not csv_file.name.endswith('.csv'):
            messages.error(request, 'File must be a CSV')
            return redirect('admin:bulk_upload')
        
        # Size validation (max 5MB)
        if csv_file.size > 5242880:
            messages.error(request, 'File size must be under 5MB')
            return redirect('admin:bulk_upload')
        
        try:
            decoded_file = csv_file.read().decode('utf-8').splitlines()
            reader = csv.DictReader(decoded_file)
            
            created_count = 0
            error_count = 0
            errors = []
            
            with transaction.atomic():
                for row_num, row in enumerate(reader, start=2):
                    try:
                        # Validate required fields
                        if not all([row.get('subtopic'), row.get('question_text'), row.get('explanation')]):
                            errors.append(f"Row {row_num}: Missing required fields")
                            error_count += 1
                            continue
                        
                        # Get or create subtopic
                        subtopic = Subtopic.objects.get(name=row['subtopic'])
                        
                        # Create question
                        question = Question.objects.create(
                            subtopic=subtopic,
                            question_text=row['question_text'],
                            explanation=row['explanation'],
                            status='DRAFT'  # Start as draft for review
                        )
                        
                        # Create answers
                        for i in range(1, 6):
                            answer_text = row.get(f'answer_{i}')
                            if answer_text:
                                Answer.objects.create(
                                    question=question,
                                    answer_text=answer_text,
                                    is_correct=row.get(f'is_correct_{i}', '').upper() == 'TRUE'
                                )
                        
                        created_count += 1
                        
                    except Subtopic.DoesNotExist:
                        errors.append(f"Row {row_num}: Subtopic '{row.get('subtopic')}' not found")
                        error_count += 1
                    except Exception as e:
                        errors.append(f"Row {row_num}: {str(e)}")
                        error_count += 1
            
            # Log the upload
            logger.info(f"Bulk upload by {request.user.username}: {created_count} questions created, {error_count} errors")
            
            if created_count > 0:
                messages.success(request, f'Successfully uploaded {created_count} questions')
            
            if errors:
                messages.warning(request, f'{error_count} errors occurred: ' + '; '.join(errors[:5]))
            
        except Exception as e:
            messages.error(request, f'Error processing CSV: {str(e)}')
            logger.error(f"CSV upload error: {str(e)}", exc_info=True)
    
    return render(request, 'admin/bulk_upload.html')

@superuser_required
def security_dashboard(request):
    """Security monitoring dashboard"""
    
    now = timezone.now()
    last_hour = now - timedelta(hours=1)
    last_24h = now - timedelta(hours=24)
    
    # Failed login attempts (you'll need to track these)
    # This requires custom logging which we'll add
    
    # Suspicious activities
    rapid_answers = UserAnswer.objects.filter(
        timestamp__gte=last_hour
    ).values('user').annotate(
        count=Count('id')
    ).filter(count__gt=100)  # More than 100 answers in an hour is suspicious
    
    # Active admin sessions
    admin_sessions = User.objects.filter(
        is_staff=True,
        last_login__gte=last_24h
    ).count()
    
    # Recent permission changes
    recent_staff_changes = User.objects.filter(
        is_staff=True,
        date_joined__gte=last_24h
    )
    
    context = {
        'rapid_answers': rapid_answers,
        'admin_sessions': admin_sessions,
        'recent_staff_changes': recent_staff_changes,
    }
    
    return render(request, 'admin/security_dashboard.html', context)

@superuser_required
def export_data(request, model_type):
    """Export data to CSV"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{model_type}_{timezone.now().date()}.csv"'
    
    writer = csv.writer(response)
    
    if model_type == 'users':
        writer.writerow(['Username', 'Email', 'Date Joined', 'Last Login', 'Membership', 'Expiry'])
        users = User.objects.select_related('profile').all()
        for user in users:
            writer.writerow([
                user.username,
                user.email,
                user.date_joined,
                user.last_login,
                getattr(user.profile, 'membership', 'N/A'),
                getattr(user.profile, 'membership_expiry_date', 'N/A')
            ])
    
    elif model_type == 'questions':
        writer.writerow(['ID', 'Question', 'Category', 'Topic', 'Subtopic', 'Status'])
        questions = Question.objects.select_related('subtopic__topic__category').all()
        for q in questions:
            writer.writerow([
                q.id,
                q.question_text[:100],
                q.subtopic.topic.category.name,
                q.subtopic.topic.name,
                q.subtopic.name,
                q.status
            ])
    
    return response
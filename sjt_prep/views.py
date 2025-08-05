import random
from datetime import datetime, timedelta
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from .models import RankingQuestion, MultipleChoiceSJTQuestion

# Constants based on the specification
EXAM_DURATION_MINUTES = 105
# Define the structure of the mock exam (adjust counts as needed)
RANKING_QUESTIONS_COUNT = 28 
MCQ_QUESTIONS_COUNT = 28
TOTAL_QUESTIONS = RANKING_QUESTIONS_COUNT + MCQ_QUESTIONS_COUNT

@login_required
def sjt_setup(request):
    """Displays information about the SJT and allows the user to start."""
    context = {
        'duration': EXAM_DURATION_MINUTES,
        'total_questions': TOTAL_QUESTIONS,
    }
    # Assumes templates are located in a folder named 'sjt_prep' within your templates directory
    return render(request, 'sjt_prep/setup.html', context)

@login_required
def start_sjt_exam(request):
    """Initializes the exam session."""
    if request.method != 'POST':
        return redirect('sjt_prep:sjt_setup')

    # 1. Fetch Questions (including pilots, filtering only by active status)
    # Fetching only IDs and pilot status for efficiency
    ranking_qs = list(RankingQuestion.objects.filter(is_active=True).only('id', 'is_pilot'))
    mcq_qs = list(MultipleChoiceSJTQuestion.objects.filter(is_active=True).only('id', 'is_pilot'))

    # Shuffle and select the required count
    random.shuffle(ranking_qs)
    random.shuffle(mcq_qs)
    
    selected_ranking = ranking_qs[:RANKING_QUESTIONS_COUNT]
    selected_mcq = mcq_qs[:MCQ_QUESTIONS_COUNT]

    # Basic check for sufficient content
    if len(selected_ranking) < RANKING_QUESTIONS_COUNT or len(selected_mcq) < MCQ_QUESTIONS_COUNT:
        messages.error(request, f"Not enough SJT questions available to start the mock exam (Requires {TOTAL_QUESTIONS}). Please contact support.")
        return redirect('sjt_prep:sjt_setup')

    # 2. Structure the Exam Session Data
    exam_questions = []
    
    # Add questions with metadata needed for the exam flow and scoring
    for q in selected_ranking:
        exam_questions.append({'type': 'ranking', 'id': q.id, 'is_pilot': q.is_pilot})
        
    for q in selected_mcq:
        exam_questions.append({'type': 'mcq', 'id': q.id, 'is_pilot': q.is_pilot})
        
    # Shuffle the combined list so types are interleaved
    random.shuffle(exam_questions)

    # 3. Initialize Session
    start_time = timezone.now()
    sjt_context = {
        'questions': exam_questions,
        'start_time': start_time.isoformat(),
        'duration_seconds': EXAM_DURATION_MINUTES * 60,
        'user_answers': {}, # Format: { "q_index": [list_of_ids_as_strings] }
    }
    
    request.session['sjt_context'] = sjt_context
    return redirect('sjt_prep:sjt_exam_player')

@login_required
def sjt_exam_player(request):
    """The main exam interface (SPA-like). Loads all questions upfront."""
    if 'sjt_context' not in request.session:
        messages.error(request, "SJT exam session not found.")
        return redirect('sjt_prep:sjt_setup')

    context = request.session['sjt_context']
    
    # Check Timer
    try:
        start_time = datetime.fromisoformat(context['start_time'])
        duration = timedelta(seconds=context['duration_seconds'])
        time_passed = timezone.now() - start_time
        seconds_remaining = max(0, int((duration - time_passed).total_seconds()))
    except (ValueError, TypeError):
        # Handle corrupted session time data
        del request.session['sjt_context']
        return redirect('sjt_prep:sjt_setup')

    if seconds_remaining <= 0:
        # Time is up, redirect to results (the view will handle the message)
        return redirect('sjt_prep:sjt_results')

    # Prepare data for the frontend
    questions_data = []
    
    # Optimization: Fetch all required questions in bulk
    ranking_ids = [q['id'] for q in context['questions'] if q['type'] == 'ranking']
    mcq_ids = [q['id'] for q in context['questions'] if q['type'] == 'mcq']
    
    # Fetch questions and prefetch their related actions/options
    ranking_qs = RankingQuestion.objects.filter(id__in=ranking_ids).prefetch_related('actions')
    mcq_qs = MultipleChoiceSJTQuestion.objects.filter(id__in=mcq_ids).prefetch_related('mcq_actions')
    
    # Create lookup dictionaries for quick access
    ranking_lookup = {q.id: q for q in ranking_qs}
    mcq_lookup = {q.id: q for q in mcq_qs}

    for index, q_meta in enumerate(context['questions']):
        q_data = {'index': index, 'type': q_meta['type']}
        question = None
        actions = []

        if q_meta['type'] == 'ranking':
            question = ranking_lookup.get(q_meta['id'])
            if question:
                actions = list(question.actions.all())
        elif q_meta['type'] == 'mcq':
            question = mcq_lookup.get(q_meta['id'])
            if question:
                actions = list(question.mcq_actions.all())

        if question:
            q_data['scenario'] = question.scenario
            # Important: Shuffle actions for the user interface so they don't see the correct order
            random.shuffle(actions)
            # Prepare action data for JSON serialization
            q_data['actions'] = [{'id': a.id, 'text': getattr(a, 'action_text', '')} for a in actions]
            questions_data.append(q_data)

    return render(request, 'sjt_prep/player.html', {
        'questions_data': questions_data,
        'seconds_remaining': seconds_remaining,
        'user_answers': context['user_answers'],
    })

@login_required
def submit_sjt_answers(request):
    """AJAX endpoint to save answers during the exam."""
    if 'sjt_context' not in request.session or request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid request or session expired'}, status=400)

    try:
        q_index = request.POST.get('q_index')
        # 'answers[]' is how lists are typically sent via FormData AJAX
        answers = request.POST.getlist('answers[]') 
        
        if q_index is None:
            return JsonResponse({'status': 'error', 'message': 'Missing index'}, status=400)

        # Save to session (treat empty list as unanswered/cleared)
        request.session['sjt_context']['user_answers'][str(q_index)] = answers
        request.session.modified = True
        
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
def sjt_results(request):
    """Calculates and displays the exam results."""
    if 'sjt_context' not in request.session:
        messages.error(request, "SJT exam session not found. Cannot display results.")
        return redirect('sjt_prep:sjt_setup')

    context = request.session['sjt_context']
    
    # Check if time expired before redirecting here
    try:
        start_time = datetime.fromisoformat(context['start_time'])
        duration = timedelta(seconds=context['duration_seconds'])
        if timezone.now() > start_time + duration:
             messages.info(request, "Time is up! The SJT exam has been automatically submitted.")
    except (ValueError, TypeError):
        pass

    user_answers = context.get('user_answers', {})
    
    total_score = 0
    max_possible_score = 0
    results_details = []

    # Optimization: Fetch all required questions in bulk for scoring
    ranking_ids = [q['id'] for q in context['questions'] if q['type'] == 'ranking']
    mcq_ids = [q['id'] for q in context['questions'] if q['type'] == 'mcq']
    
    ranking_qs = RankingQuestion.objects.filter(id__in=ranking_ids).prefetch_related('actions')
    mcq_qs = MultipleChoiceSJTQuestion.objects.filter(id__in=mcq_ids).prefetch_related('mcq_actions')
    
    ranking_lookup = {q.id: q for q in ranking_qs}
    mcq_lookup = {q.id: q for q in mcq_qs}

    for index, q_meta in enumerate(context['questions']):
        q_index_str = str(index)
        submitted_answer_ids = user_answers.get(q_index_str, [])
        
        detail = {'index': index + 1, 'type': q_meta['type'], 'is_pilot': q_meta['is_pilot']}
        question = None
        score = 0
        max_score = 0

        if q_meta['type'] == 'ranking':
            question = ranking_lookup.get(q_meta['id'])
            if question:
                # Calculate score using the model method
                score = question.calculate_score(submitted_answer_ids)
                max_score = question.MAX_SCORE
                
                # Detailed actions feedback for results page
                actions_feedback = []
                # Ensure correct order for display (model Meta ordering handles this)
                correct_order = question.actions.all()
                for action in correct_order:
                    try:
                        # Find the rank the user gave this action (IDs are stored as strings)
                        user_rank = submitted_answer_ids.index(str(action.id)) + 1
                    except ValueError:
                        user_rank = "Not Ranked"
                        
                    actions_feedback.append({
                        'text': action.action_text,
                        'correct_rank': action.correct_rank,
                        'user_rank': user_rank
                    })
                detail['actions'] = actions_feedback

        elif q_meta['type'] == 'mcq':
            question = mcq_lookup.get(q_meta['id'])
            if question:
                # Calculate score using the model method
                score = question.calculate_score(submitted_answer_ids)
                max_score = question.MAX_SCORE

                # Detailed actions feedback for results page
                actions_feedback = []
                for action in question.mcq_actions.all():
                    # IDs are stored as strings in the session
                    user_selected = str(action.id) in submitted_answer_ids
                    actions_feedback.append({
                        'text': action.action_text,
                        'is_correct': action.is_correct,
                        'user_selected': user_selected
                    })
                detail['actions'] = actions_feedback

        if question:
            detail['scenario'] = question.scenario
            detail['rationale'] = question.rationale
            detail['score'] = score
            detail['max_score'] = max_score
            results_details.append(detail)

            # Accumulate scores only if it's not a pilot question
            if not q_meta['is_pilot']:
                total_score += score
                max_possible_score += max_score

    # Clean up the session
    if 'sjt_context' in request.session:
        del request.session['sjt_context']
    
    percentage = (total_score / max_possible_score * 100) if max_possible_score > 0 else 0

    return render(request, 'sjt_prep/results.html', {
        'total_score': total_score,
        'max_possible_score': max_possible_score,
        'percentage': round(percentage, 2),
        'results_details': results_details,
    })
from django.db import models
from django.contrib.auth.models import User
from simple_history.models import HistoricalRecords

class SJTAttribute(models.Model):
    """Categorization for SJT questions (e.g., Integrity, Resilience, Teamwork)."""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

class SJTQuestionBase(models.Model):
    """Abstract base model for all SJT question types."""
    attribute = models.ForeignKey(SJTAttribute, on_delete=models.SET_NULL, null=True, blank=True)
    scenario = models.TextField(help_text="The situation presented to the candidate.")
    rationale = models.TextField(help_text="Detailed explanation of the correct answers/ranking.")
    is_pilot = models.BooleanField(default=False, help_text="Pilot questions are included in the exam but not scored.")
    is_active = models.BooleanField(default=True)
    
    # History tracking for audit (inherited by concrete models)
    history = HistoricalRecords(inherit=True)

    class Meta:
        abstract = True

    def __str__(self):
        return self.scenario[:50] + "..."

# --- Ranking Question Models ---

class RankingQuestion(SJTQuestionBase):
    """A question where the user must rank 4-5 actions."""
    
    # Constants for scoring based on proximity to the correct rank.
    # (Distance from correct rank): points awarded
    SCORING_MATRIX = {
        0: 4, # Correct position
        1: 3, # 1 position away (near-miss)
        2: 2, # 2 positions away
        3: 1, # 3 positions away
        4: 0  # 4 positions away
    }
    # Assuming 5 options, max score is 20 (5 actions * 4 points)
    MAX_SCORE = 20 

    def calculate_score(self, user_ranking_ids):
        """
        Calculates the score based on the user's ranking proximity.
        user_ranking_ids: A list of RankableAction IDs (as strings) in the order the user ranked them.
        """
        if not user_ranking_ids:
            return 0

        actions = self.actions.all()
        score = 0
        
        # Create a map of {action_id: correct_rank}
        correct_ranks = {action.id: action.correct_rank for action in actions}
        
        # Iterate through the user's submitted ranking
        for index, action_id_str in enumerate(user_ranking_ids):
            user_rank = index + 1 # 1-based rank
            try:
                action_id = int(action_id_str) 
                correct_rank = correct_ranks.get(action_id)
                
                if correct_rank is not None:
                    # Calculate distance and look up score from the matrix
                    distance = abs(user_rank - correct_rank)
                    score += self.SCORING_MATRIX.get(distance, 0)
            except ValueError:
                continue # Handle invalid IDs if necessary

        return score


class RankableAction(models.Model):
    """An action associated with a RankingQuestion."""
    question = models.ForeignKey(RankingQuestion, on_delete=models.CASCADE, related_name='actions')
    action_text = models.CharField(max_length=500)
    correct_rank = models.PositiveSmallIntegerField(help_text="The correct rank (1=Most Appropriate, 5=Least Appropriate)")

    class Meta:
        ordering = ['correct_rank']
        # Ensure ranks are unique per question
        unique_together = ('question', 'correct_rank')

    def __str__(self):
        return f"Rank {self.correct_rank}: {self.action_text[:50]}..."

# --- Multiple Choice SJT Question Models ---

class MultipleChoiceSJTQuestion(SJTQuestionBase):
    """A question where the user must select the best 3 options."""
    
    POINTS_PER_CORRECT = 4
    MAX_SCORE = 12 # 3 correct options * 4 points
    REQUIRED_SELECTIONS = 3

    def calculate_score(self, selected_action_ids):
        """
        Calculates the score. 0 points if the number of selections is incorrect.
        """
        # Based on spec: "If the user selects more than three options, they score zero."
        if not selected_action_ids or len(selected_action_ids) > self.REQUIRED_SELECTIONS:
            return 0
        
        score = 0
        # Get the IDs of the correct actions for this question
        correct_ids = set(self.mcq_actions.filter(is_correct=True).values_list('id', flat=True))
        
        for action_id_str in selected_action_ids:
            try:
                action_id = int(action_id_str)
                if action_id in correct_ids:
                    score += self.POINTS_PER_CORRECT
            except ValueError:
                continue
                
        return score


class MCQAction(models.Model):
    """An option associated with a MultipleChoiceSJTQuestion."""
    question = models.ForeignKey(MultipleChoiceSJTQuestion, on_delete=models.CASCADE, related_name='mcq_actions')
    action_text = models.CharField(max_length=500)
    is_correct = models.BooleanField(default=False, help_text="Check if this is one of the 3 best options.")

    def __str__(self):
        return f"{'[Correct] ' if self.is_correct else ''}{self.action_text[:50]}..."
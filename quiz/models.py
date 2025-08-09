# quiz/models.py

from django.db import models
from django.contrib.auth.models import User
# Import HistoricalRecords
from simple_history.models import HistoricalRecords
from django.utils.text import Truncator # Import Truncator

# Model for the main subject categories (e.g., Preclinical, Clinical)
class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    history = HistoricalRecords() # Add History Tracking

    def __str__(self):
        return self.name
     
    class Meta:
        verbose_name_plural = "Categories"


# Model for the main topics (e.g., Anatomy, Pharmacology)
class Topic(models.Model):
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='topics')
    name = models.CharField(max_length=100)
    history = HistoricalRecords() # Add History Tracking

    def __str__(self):
        return f"{self.category.name} - {self.name}"


# Model for the subtopics (e.g., Head and Neck Anatomy)
class Subtopic(models.Model):
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name='subtopics')
    name = models.CharField(max_length=100)
    history = HistoricalRecords() # Add History Tracking

    def __str__(self):
        return self.name


# Model for the actual questions
class Question(models.Model):
    subtopic = models.ForeignKey(Subtopic, on_delete=models.CASCADE, related_name='questions')
    question_text = models.TextField()
    question_image = models.ImageField(upload_to='question_images/', blank=True, null=True)
    explanation = models.TextField(help_text="Detailed explanation for the correct answer.")
    history = HistoricalRecords() # Add History Tracking

    def __str__(self):
        # Use Truncator for cleaner representation
        return Truncator(self.question_text).chars(50)


# Model for the answer options for a given question
class Answer(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='answers')
    answer_text = models.CharField(max_length=500)
    is_correct = models.BooleanField(default=False)
    # Adding history here as well for comprehensive tracking of answer changes
    history = HistoricalRecords() 

    def __str__(self):
        return f"Answer for Q: {self.question.id} | Correct: {self.is_correct}"


# Model to track user performance (Transactional data)
class UserAnswer(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    is_correct = models.BooleanField()
    # auto_now=True updates the timestamp every time the object is saved (useful for tracking latest attempts)
    timestamp = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'question')

    def __str__(self):
        return f"{self.user.username}'s answer to Q:{self.question.id} is {'Correct' if self.is_correct else 'Incorrect'}"


# (QuestionReport, ContactInquiry, FlaggedQuestion models remain the same as original)
# Model for question reports
class QuestionReport(models.Model):
    REPORT_STATUS_CHOICES = [
        ('OPEN', 'Open'),
        ('REVIEWING', 'Under Review'),
        ('RESOLVED', 'Resolved'),
    ]
     
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='reports')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    reason = models.TextField(help_text="User's reason for reporting the question.")
    status = models.CharField(max_length=10, choices=REPORT_STATUS_CHOICES, default='OPEN')
    reported_at = models.DateTimeField(auto_now_add=True)
    history = HistoricalRecords() # Add History Tracking (to track status changes)

    def __str__(self):
        return f"Report for Q:{self.question.id} by {self.user.username}"

    class Meta:
        unique_together = ('question', 'user')


# Model for contact inquiries
class ContactInquiry(models.Model):
    INQUIRY_STATUS_CHOICES = [
        ('NEW', 'New'),
        ('RESPONDED', 'Responded'),
        ('CLOSED', 'Closed'),
    ]

    name = models.CharField(max_length=100)
    email = models.EmailField()
    subject = models.CharField(max_length=200)
    message = models.TextField()
    status = models.CharField(max_length=10, choices=INQUIRY_STATUS_CHOICES, default='NEW')
    submitted_at = models.DateTimeField(auto_now_add=True)
    history = HistoricalRecords() # Add History Tracking (to track status changes)

    def __str__(self):
        return f"Inquiry from {self.name} re: {self.subject}"
     
    class Meta:
        verbose_name_plural = "Contact Inquiries"


# Model to permanently store user's flagged questions (Transactional data)
class FlaggedQuestion(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'question')

    def __str__(self):
        return f"{self.user.username} flagged Q:{self.question.id}"
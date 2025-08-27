# quiz/models.py
from django.db import models
from django.contrib.auth.models import User
from simple_history.models import HistoricalRecords
from django.utils.text import Truncator
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
import os

def validate_image_file(file):
    """Validate uploaded image files for security"""
    # Check file size (max 2MB)
    max_size = 2 * 1024 * 1024  # 2MB
    if file.size > max_size:
        raise ValidationError(f'File size must not exceed 2MB. Current size: {file.size / (1024*1024):.2f}MB')
    
    # Check file extension
    valid_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
    ext = os.path.splitext(file.name)[1].lower()
    if ext not in valid_extensions:
        raise ValidationError(f'Invalid file extension. Allowed: {", ".join(valid_extensions)}')
    
    # Skip MIME type checking since python-magic is problematic on Render
    # The extension check and Django's built-in image validation should be sufficient
    
    return file

# Model for the main subject categories (e.g., Preclinical, Clinical)
class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    history = HistoricalRecords()
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name_plural = "Categories"

# Model for the main topics (e.g., Anatomy, Pharmacology)
class Topic(models.Model):
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='topics')
    name = models.CharField(max_length=100)
    history = HistoricalRecords()
    
    def __str__(self):
        return f"{self.category.name} - {self.name}"

# Model for the subtopics (e.g., Head and Neck Anatomy)
class Subtopic(models.Model):
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name='subtopics')
    name = models.CharField(max_length=100)
    history = HistoricalRecords()
    
    def __str__(self):
        return self.name

# Model for the actual questions
class Question(models.Model):
    STATUS_CHOICES = [
        ('DRAFT', 'Draft (Admin Only)'),
        ('LIVE', 'Live (Visible to Users)'),
    ]
    
    subtopic = models.ForeignKey(Subtopic, on_delete=models.CASCADE, related_name='questions')
    question_text = models.TextField()
    question_image = models.ImageField(
        upload_to='question_images/',
        blank=True,
        null=True,
        validators=[
            FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'gif', 'webp']),
            validate_image_file
        ],
        help_text="Max file size: 2MB. Allowed formats: JPG, PNG, GIF, WebP"
    )
    explanation = models.TextField(help_text="Detailed explanation for the correct answer.")
    status = models.CharField(
        max_length=5,
        choices=STATUS_CHOICES,
        default='DRAFT',
        help_text="Only 'Live' questions are shown to users."
    )
    history = HistoricalRecords()
    
    def __str__(self):
        return Truncator(self.question_text).chars(50)
    
    def clean(self):
        """Additional validation"""
        super().clean()
        if self.question_image:
            try:
                validate_image_file(self.question_image)
            except ValidationError as e:
                raise ValidationError({'question_image': e})

# Model for the answer options for a given question
class Answer(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='answers')
    answer_text = models.CharField(max_length=500)
    is_correct = models.BooleanField(default=False)
    history = HistoricalRecords()
    
    def __str__(self):
        return f"Answer for Q: {self.question.id} | Correct: {self.is_correct}"

# Model to track user performance
class UserAnswer(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    is_correct = models.BooleanField()
    timestamp = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('user', 'question')
    
    def __str__(self):
        return f"{self.user.username}'s answer to Q:{self.question.id} is {'Correct' if self.is_correct else 'Incorrect'}"

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
    history = HistoricalRecords()
    
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
    history = HistoricalRecords()
    
    def __str__(self):
        return f"Inquiry from {self.name} re: {self.subject}"
    
    class Meta:
        verbose_name_plural = "Contact Inquiries"

# Model to permanently store user's flagged questions
class FlaggedQuestion(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('user', 'question')
    
    def __str__(self):
        return f"{self.user.username} flagged Q:{self.question.id}"
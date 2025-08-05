# quiz/admin.py

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.text import Truncator # Import Truncator for the fix
# Ensure FlaggedQuestion is imported
from .models import Category, Topic, Subtopic, Question, Answer, UserAnswer, QuestionReport, ContactInquiry, FlaggedQuestion

# Import for History/Audit Log
from simple_history.admin import SimpleHistoryAdmin
# Import for Date Range Filter
from rangefilter.filters import DateTimeRangeFilter

# --- Helper Function for Clickable Links (A. Functionality) ---
def get_admin_link(obj, display_text=None):
    """Generates a clickable admin change URL for a given object."""
    if not obj:
        return "-"
    try:
        app_label = obj._meta.app_label
        model_name = obj._meta.model_name
        # Construct the URL name for the admin change view
        url_name = f'admin:{app_label}_{model_name}_change'
        url = reverse(url_name, args=[obj.pk])
        display = display_text if display_text else str(obj)
        # Return HTML link
        return format_html('<a href="{}">{}</a>', url, display)
    except Exception:
        # Fallback if URL reverse fails (e.g., model not registered)
        return str(obj)

# --- Model Admins ---

class AnswerInline(admin.TabularInline):
    model = Answer
    extra = 1 # Reduced extra slots from 3 to 1 for a cleaner interface

# Inherit from SimpleHistoryAdmin
@admin.register(Question)
class QuestionAdmin(SimpleHistoryAdmin):
    fieldsets = [
        ('Question Information', {'fields': ['subtopic', 'question_text', 'question_image']}),
        ('Explanation', {'fields': ['explanation']}),
    ]
    inlines = [AnswerInline]
    
    # A. Functionality: Display Topic and Category
    list_display = ('question_text_short', 'subtopic', 'get_topic', 'get_category')
    
    # A. Functionality: Add hierarchical filters
    list_filter = ['subtopic__topic__category', 'subtopic__topic', 'subtopic']
    search_fields = ['question_text', 'explanation']
    
    # B. Performance: Optimize queries by selecting related fields up to Category
    list_select_related = ('subtopic__topic__category',)

    def question_text_short(self, obj):
        return str(obj)
    question_text_short.short_description = 'Question Text'

    def get_topic(self, obj):
        return obj.subtopic.topic.name
    get_topic.short_description = 'Topic'
    get_topic.admin_order_field = 'subtopic__topic__name'

    def get_category(self, obj):
        return obj.subtopic.topic.category.name
    get_category.short_description = 'Category'
    get_category.admin_order_field = 'subtopic__topic__category__name'

@admin.register(UserAnswer)
class UserAnswerAdmin(admin.ModelAdmin): # History not typically needed on this transactional model
    # A. Functionality: Use clickable links
    list_display = ('user_link', 'question_link', 'is_correct', 'timestamp')
    # ENHANCEMENT: Add Date Range Filter
    list_filter = ('is_correct', ('timestamp', DateTimeRangeFilter))
    # Prevent editing of answers via admin for data integrity
    readonly_fields = ('user', 'question', 'is_correct', 'timestamp') 
    search_fields = ('user__username', 'question__question_text')
    
    # B. Performance
    list_select_related = ('user', 'question')

    def user_link(self, obj):
        return get_admin_link(obj.user)
    user_link.short_description = 'User'

    def question_link(self, obj):
        return get_admin_link(obj.question)
    question_link.short_description = 'Question'


@admin.register(QuestionReport)
# Inherit from SimpleHistoryAdmin
class QuestionReportAdmin(SimpleHistoryAdmin):
    # FIX: Added 'get_reason_short' to list_display
    list_display = ('question_link', 'user_link', 'get_reason_short', 'status', 'reported_at')
    # ENHANCEMENT: Add Date Range Filter
    list_filter = ('status', ('reported_at', DateTimeRangeFilter))
    search_fields = ('question__question_text', 'user__username', 'reason')
    # Keep these readonly in the edit view (including reason)
    readonly_fields = ('question', 'user', 'reported_at', 'reason') 
    list_editable = ('status',)
    
    # B. Performance
    list_select_related = ('user', 'question')

    # FIX: Method to display truncated reason using Django Truncator
    def get_reason_short(self, obj):
        return Truncator(obj.reason).chars(100)
    get_reason_short.short_description = 'Reason Summary'

    def user_link(self, obj):
        return get_admin_link(obj.user)
    user_link.short_description = 'User'

    def question_link(self, obj):
        # Displaying the QID is often more useful in reports
        return get_admin_link(obj.question, display_text=f"QID: {obj.question.id}")
    question_link.short_description = 'Question'


@admin.register(ContactInquiry)
# Inherit from SimpleHistoryAdmin
class ContactInquiryAdmin(SimpleHistoryAdmin):
    list_display = ('subject', 'name', 'email', 'status', 'submitted_at')
    # ENHANCEMENT: Add Date Range Filter
    list_filter = ('status', ('submitted_at', DateTimeRangeFilter))
    search_fields = ('name', 'email', 'subject', 'message')
    readonly_fields = ('name', 'email', 'subject', 'message', 'submitted_at')
    list_editable = ('status',)

# Register standard models (using decorators for consistency and enhancements)

@admin.register(Category)
class CategoryAdmin(SimpleHistoryAdmin):
    search_fields = ('name',)

@admin.register(Topic)
class TopicAdmin(SimpleHistoryAdmin):
    list_display = ('name', 'category')
    list_filter = ('category',)
    list_select_related = ('category',)
    search_fields = ('name', 'category__name')

@admin.register(Subtopic)
class SubtopicAdmin(SimpleHistoryAdmin):
    list_display = ('name', 'topic', 'get_category')
    list_filter = ('topic__category', 'topic')
    list_select_related = ('topic__category',)
    search_fields = ('name', 'topic__name')

    def get_category(self, obj):
        return obj.topic.category.name
    get_category.short_description = 'Category'
    get_category.admin_order_field = 'topic__category__name'


# Register FlaggedQuestion for visibility
@admin.register(FlaggedQuestion)
class FlaggedQuestionAdmin(admin.ModelAdmin):
    list_display = ('user_link', 'question_link', 'timestamp')
    list_select_related = ('user', 'question')
    search_fields = ('user__username', 'question__question_text')
    readonly_fields = ('user', 'question', 'timestamp')
    # ENHANCEMENT: Add Date Range Filter
    list_filter = (('timestamp', DateTimeRangeFilter),)

    def user_link(self, obj):
        return get_admin_link(obj.user)
    user_link.short_description = 'User'

    def question_link(self, obj):
        return get_admin_link(obj.question)
    question_link.short_description = 'Question'
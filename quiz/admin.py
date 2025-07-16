# quiz/admin.py

from django.contrib import admin
from .models import Category, Topic, Subtopic, Question, Answer, UserAnswer, QuestionReport, ContactInquiry

class AnswerInline(admin.TabularInline):
    model = Answer
    extra = 3 

class QuestionAdmin(admin.ModelAdmin):
    fieldsets = [
        ('Question Information', {'fields': ['subtopic', 'question_text', 'question_image']}),
        ('Explanation', {'fields': ['explanation']}),
    ]
    inlines = [AnswerInline]
    list_filter = ['subtopic']
    search_fields = ['question_text']

class UserAnswerAdmin(admin.ModelAdmin):
    list_display = ('user', 'question', 'is_correct', 'timestamp')
    list_filter = ('user', 'is_correct')
    readonly_fields = ('user', 'question', 'is_correct', 'timestamp') 

# Register your models here
admin.site.register(Category)
admin.site.register(Topic)
admin.site.register(Subtopic)
admin.site.register(Question, QuestionAdmin)
admin.site.register(UserAnswer, UserAnswerAdmin)

@admin.register(QuestionReport)
# THIS LINE IS NOW CORRECTED
class QuestionReportAdmin(admin.ModelAdmin):
    list_display = ('question', 'user', 'status', 'reported_at')
    list_filter = ('status',)
    search_fields = ('question__question_text', 'user__username', 'reason')
    readonly_fields = ('question', 'user', 'reported_at')
    list_editable = ('status',)

@admin.register(ContactInquiry)
class ContactInquiryAdmin(admin.ModelAdmin):
    list_display = ('subject', 'name', 'email', 'status', 'submitted_at')
    list_filter = ('status',)
    search_fields = ('name', 'email', 'subject', 'message')
    readonly_fields = ('name', 'email', 'subject', 'message', 'submitted_at')
    list_editable = ('status',)
from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin
from .models import SJTAttribute, RankingQuestion, RankableAction, MultipleChoiceSJTQuestion, MCQAction

@admin.register(SJTAttribute)
class SJTAttributeAdmin(admin.ModelAdmin):
    list_display = ('name',)

# --- Ranking Admin ---

class RankableActionInline(admin.TabularInline):
    model = RankableAction
    extra = 5
    max_num = 5
    # Ensures actions are displayed in the correct order in the admin editor
    ordering = ('correct_rank',)

@admin.register(RankingQuestion)
class RankingQuestionAdmin(SimpleHistoryAdmin):
    list_display = ('scenario_short', 'attribute', 'is_pilot', 'is_active')
    list_filter = ('attribute', 'is_pilot', 'is_active')
    inlines = [RankableActionInline]
    search_fields = ('scenario', 'rationale')

    def scenario_short(self, obj):
        return str(obj)
    scenario_short.short_description = 'Scenario'

# --- Multiple Choice Admin ---

class MCQActionInline(admin.TabularInline):
    model = MCQAction
    extra = 8
    max_num = 8 # SJT typically has up to 8 options

@admin.register(MultipleChoiceSJTQuestion)
class MultipleChoiceSJTQuestionAdmin(SimpleHistoryAdmin):
    list_display = ('scenario_short', 'attribute', 'is_pilot', 'is_active')
    list_filter = ('attribute', 'is_pilot', 'is_active')
    inlines = [MCQActionInline]
    search_fields = ('scenario', 'rationale')

    def scenario_short(self, obj):
        return str(obj)
    scenario_short.short_description = 'Scenario'
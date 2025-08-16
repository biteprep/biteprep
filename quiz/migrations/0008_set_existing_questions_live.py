# quiz/migrations/0008_set_existing_questions_live.py

from django.db import migrations

def set_status_to_live(apps, schema_editor):
    # Get the model definitions at this point in the migration history
    Question = apps.get_model('quiz', 'Question')
    HistoricalQuestion = apps.get_model('quiz', 'HistoricalQuestion')

    # Update all existing questions currently marked as DRAFT (the default) to LIVE status
    Question.objects.filter(status='DRAFT').update(status='LIVE')
    
    # Update the history records as well to maintain consistency
    HistoricalQuestion.objects.filter(status='DRAFT').update(status='LIVE')

def reverse_status(apps, schema_editor):
    # Optional: Define how to reverse this migration (set back to DRAFT)
    Question = apps.get_model('quiz', 'Question')
    HistoricalQuestion = apps.get_model('quiz', 'HistoricalQuestion')
    Question.objects.filter(status='LIVE').update(status='DRAFT')
    HistoricalQuestion.objects.filter(status='LIVE').update(status='DRAFT')


class Migration(migrations.Migration):

    # Depends on the migration that added the status field (0007)
    dependencies = [
        ('quiz', '0007_add_question_status'),
    ]

    operations = [
        # Run the data migration function
        migrations.RunPython(set_status_to_live, reverse_code=reverse_status),
    ]
import csv
from django.core.management.base import BaseCommand, CommandError
from quiz.models import Question, Answer, Subtopic

class Command(BaseCommand):
    help = 'Imports questions from a specified CSV file.'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='The path to the CSV file to import.')

    def handle(self, *args, **options):
        csv_file_path = options['csv_file']
        
        try:
            with open(csv_file_path, mode='r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                
                for i, row in enumerate(reader):
                    line_num = i + 2 # Account for header row
                    try:
                        # --- Get required fields ---
                        subtopic_name = row['subtopic_name']
                        question_text = row['question_text']
                        explanation = row['explanation']

                        if not all([subtopic_name, question_text, explanation]):
                            self.stdout.write(self.style.WARNING(f'Skipping line {line_num}: missing required data.'))
                            continue
                        
                        # --- Find the subtopic ---
                        try:
                            subtopic = Subtopic.objects.get(name__iexact=subtopic_name)
                        except Subtopic.DoesNotExist:
                            self.stdout.write(self.style.ERROR(f'Line {line_num}: Subtopic "{subtopic_name}" not found. Skipping question.'))
                            continue
                        
                        # --- Create the Question ---
                        question, created = Question.objects.update_or_create(
                            question_text=question_text,
                            subtopic=subtopic,
                            defaults={'explanation': explanation}
                        )

                        if created:
                            self.stdout.write(self.style.SUCCESS(f'Line {line_num}: Created new question: "{question_text[:50]}..."'))
                        else:
                            self.stdout.write(self.style.NOTICE(f'Line {line_num}: Updated existing question: "{question_text[:50]}..."'))
                            question.answers.all().delete()

                        # --- Create Answers ---
                        for i in range(1, 6):
                            answer_text = row.get(f'answer_{i}')
                            is_correct_str = row.get(f'is_correct_{i}', 'FALSE').upper()
                            
                            if answer_text:
                                is_correct = (is_correct_str == 'TRUE')
                                # THE BUG WAS HERE. Changed 'text=' to 'answer_text='.
                                # I am assuming the field name is 'answer_text'.
                                # If this fails, I need to see your quiz/models.py file.
                                Answer.objects.create(
                                    question=question,
                                    answer_text=answer_text, 
                                    is_correct=is_correct
                                )
                                
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'Error processing line {line_num}: {e}'))

        except FileNotFoundError:
            raise CommandError(f'File "{csv_file_path}" does not exist.')

        self.stdout.write(self.style.SUCCESS('Successfully completed importing questions.'))
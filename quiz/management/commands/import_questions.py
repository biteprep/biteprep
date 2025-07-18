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
                    line_num = i + 2
                    try:
                        subtopic_name = row['subtopic_name']
                        question_text = row['question_text']
                        explanation = row['explanation']

                        if not all([subtopic_name, question_text, explanation]):
                            self.stdout.write(self.style.WARNING(f'Skipping line {line_num}: missing required data.'))
                            continue
                        
                        try:
                            subtopic = Subtopic.objects.get(name__iexact=subtopic_name)
                        except Subtopic.DoesNotExist:
                            self.stdout.write(self.style.ERROR(f'Line {line_num}: Subtopic "{subtopic_name}" not found. Skipping.'))
                            continue
                        
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

                        for i in range(1, 6):
                            answer_text = row.get(f'answer_{i}')
                            
                            if answer_text:
                                # THE BUG WAS HERE. This line now handles empty cells safely.
                                is_correct_str = row.get(f'is_correct_{i}') or 'FALSE'
                                is_correct = (is_correct_str.upper() == 'TRUE')
                                
                                # I am assuming the field name in your Answer model is 'text'.
                                # If this fails, the error will tell us the correct name.
                                Answer.objects.create(
                                    question=question,
                                    text=answer_text, 
                                    is_correct=is_correct
                                )
                                
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'Error processing line {line_num}: {e}'))

        except FileNotFoundError:
            raise CommandError(f'File "{csv_file_path}" does not exist.')

        self.stdout.write(self.style.SUCCESS('Successfully completed importing questions.'))
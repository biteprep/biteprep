import csv
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from quiz.models import Question, Answer, Subtopic

class Command(BaseCommand):
    help = 'Imports questions from a specified CSV file robustly.'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='The path to the CSV file to import.')

    def handle(self, *args, **options):
        csv_file_path = options['csv_file']
        
        rows_processed = 0
        rows_skipped = 0

        try:
            # Use 'utf-8-sig' to handle potential BOM (Byte Order Mark).
            # Use newline='' as recommended when working with the csv module.
            with open(csv_file_path, mode='r', encoding='utf-8-sig', newline='') as file:
                reader = csv.DictReader(file)
                
                # --- Header Validation ---
                if reader.fieldnames is None:
                    raise CommandError("CSV file is empty or invalid.")
                    
                required_headers = ['subtopic_name', 'question_text', 'explanation']
                if not all(h in reader.fieldnames for h in required_headers):
                    missing = set(required_headers) - set(reader.fieldnames)
                    raise CommandError(f"Missing required headers in CSV: {missing}")

                # --- Row Processing Loop ---
                for i, row in enumerate(reader):
                    # +1 for header, +1 for 1-based indexing
                    line_num = i + 2 
                    try:
                        # CRITICAL: Use a transaction to ensure atomicity.
                        # Either the question and all answers are imported, or none are.
                        with transaction.atomic():
                            self.process_row(row, line_num)
                            rows_processed += 1
                                
                    except ValueError as ve:
                        # Catches specific validation errors raised in process_row. 
                        # The transaction is automatically rolled back by Django upon exiting the 'with' block due to the exception.
                        self.stdout.write(self.style.WARNING(f'Skipping line {line_num}: {ve}. Transaction rolled back.'))
                        rows_skipped += 1
                    except Exception as e:
                        # Catches unexpected errors (e.g. database connection issues)
                        self.stdout.write(self.style.ERROR(f'Unexpected error processing line {line_num}: {e}. Transaction rolled back.'))
                        rows_skipped += 1

        except FileNotFoundError:
            raise CommandError(f'File "{csv_file_path}" does not exist.')
        except csv.Error as e:
            raise CommandError(f'CSV format error: {e}')

        self.stdout.write(self.style.SUCCESS(f'\nImport completed.\nSuccessful rows: {rows_processed}.\nSkipped rows: {rows_skipped}.'))

    def process_row(self, row, line_num):
        """Processes a single row from the CSV. 
           Raises ValueError if the data is invalid, triggering a transaction rollback in the handle method.
        """
        
        # 1. Data Extraction and Cleaning (using .strip() to remove whitespace)
        subtopic_name = row.get('subtopic_name', '').strip()
        question_text = row.get('question_text', '').strip()
        explanation = row.get('explanation', '').strip()

        # 2. Basic Validation
        if not all([subtopic_name, question_text, explanation]):
            # We raise ValueError to ensure the transaction is rolled back.
            raise ValueError('Missing required data (Subtopic, Question Text, or Explanation).')
        
        # 3. Fetch Subtopic
        try:
            subtopic = Subtopic.objects.get(name__iexact=subtopic_name)
        except Subtopic.DoesNotExist:
            raise ValueError(f'Subtopic "{subtopic_name}" not found.')
        
        # 4. Process Answers and Validate Input
        answers_buffer = []
        has_correct_answer = False

        for i in range(1, 6):
            # Clean inputs
            answer_text_val = row.get(f'answer_{i}', '').strip()
            is_correct_str = row.get(f'is_correct_{i}', '').strip().upper()

            # Skip empty answer slots
            if not answer_text_val:
                continue

            # Validate the is_correct field rigorously
            if is_correct_str == 'TRUE':
                is_correct = True
                has_correct_answer = True
            elif is_correct_str == 'FALSE' or is_correct_str == '':
                # Default to FALSE if empty or explicitly FALSE
                is_correct = False
            else:
                # If the value is something else (e.g., 'yes', '1', 'T'), reject the row.
                raise ValueError(
                    f'Invalid value for is_correct_{i} ("{is_correct_str}"). Must be "TRUE" or "FALSE".'
                )

            # Prepare the Answer object (but don't save it yet)
            # We don't assign the question yet, as we might rollback the question creation.
            answers_buffer.append(
                Answer(
                    answer_text=answer_text_val,
                    is_correct=is_correct
                )
            )

        # 5. Final Integrity Checks
        if not answers_buffer:
            raise ValueError("Question has no answers provided.")
            
        if not has_correct_answer:
            raise ValueError("Question has no answer marked as correct.")

        # 6. Create/Update Question
        # If validation passes, we proceed with database creation/update.
        question, created = Question.objects.update_or_create(
            question_text=question_text,
            subtopic=subtopic,
            defaults={'explanation': explanation}
        )

        if created:
            self.stdout.write(self.style.SUCCESS(f'Line {line_num}: Created question.'))
        else:
            # If updating, we must clear existing answers first to ensure the CSV is the source of truth.
            # This is safe because we are inside a transaction.
            self.stdout.write(self.style.NOTICE(f'Line {line_num}: Updated existing question. Replacing answers.'))
            question.answers.all().delete()

        # 7. Create Answers
        # Link the buffered answers to the question instance
        for answer in answers_buffer:
            answer.question = question
            
        # We use bulk_create for efficiency
        Answer.objects.bulk_create(answers_buffer)
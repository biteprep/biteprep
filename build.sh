#!/usr/bin/env bash
# exit on error
set -o errexit

# Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Run Django commands
python manage.py migrate

# Create superuser if it doesn't exist
python manage.py createsuperuser --no-input --username $ADMIN_USERNAME --email biteprep@outlook.com || true

# Set admin password
python manage.py set_admin_password

# Collect static files
python manage.py collectstatic --no-input
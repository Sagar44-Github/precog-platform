"""Entry point for a production server such as gunicorn:  gunicorn --workers 1 --threads 4 wsgi:application"""

from run_app import create_app

application = create_app()

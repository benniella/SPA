"""Infrastructure adapters.

The only package permitted to import SQLAlchemy, boto3, Celery and similar. Each
adapter implements a port declared in 'app.application.ports'.
"""

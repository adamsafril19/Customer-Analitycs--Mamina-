"""
Celery Tasks Package

Configuration and initialization for Celery background tasks.
"""
import os
from celery import Celery

# Create Celery app
celery_app = Celery(
    "mamina_churn",
    broker=os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0"),
    include=[
        "app.tasks.etl_tasks",
        "app.tasks.prediction_tasks"
    ]
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Jakarta",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 minutes
    task_soft_time_limit=240,  # 4 minutes (for graceful shutdown)
    worker_prefetch_multiplier=1,
    task_acks_late=True,
)


def init_celery(app):
    """
    Initialize Celery with Flask application context
    
    Args:
        app: Flask application instance
    """
    celery_app.conf.update(
        broker_url=app.config.get("CELERY_BROKER_URL"),
        result_backend=app.config.get("CELERY_RESULT_BACKEND")
    )
    
    class ContextTask(celery_app.Task):
        """Make Celery tasks run within Flask application context"""
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)
    
    celery_app.Task = ContextTask
    
    return celery_app

from celery import shared_task


@shared_task
def example_task():
    # Just a placeholder for demonstration
    return "Task service celery task executed."

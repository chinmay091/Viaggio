"""
Celery tasks for activity domain: hourly aggregation and weekly baselines (P3-F4).
"""

from celery import shared_task

from apps.activity.services import aggregate_activity, refresh_area_context, recompute_baselines


@shared_task(name="activity.aggregate_hourly")
def aggregate_hourly():
    """
    Periodic task to aggregate UserActivity into 5-minute ActivityAggregate
    buckets for the last hour and prune rows older than 28 days (P3-D4).
    Triggered hourly at minute :02 via Celery Beat.
    """
    return aggregate_activity()


@shared_task(name="activity.recompute_baselines")
def recompute_baselines_task():
    """
    Periodic task to recompute historical baselines from aggregates over the
    last 8 weeks (56 days) (P3-D5).
    Triggered weekly on Sunday at 02:30 IST via Celery Beat.
    """
    return recompute_baselines()


@shared_task(name="activity.refresh_area_context")
def refresh_area_context_task():
    """
    Periodic task to precompute ``geo.AreaContext`` for the top res8 cells by
    last-hour check-ins (rule-based summary, P3-D7).
    Triggered hourly at minute :35 via Celery Beat.
    """
    return refresh_area_context()

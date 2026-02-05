import asyncio
import logging
from typing import Optional

log = logging.getLogger(__name__)


async def reconcile_loop(interval_seconds: int, stop_event: Optional[asyncio.Event] = None):
    """Run reconcile_pending_purchases periodically until stop_event is set (if provided).

    This function deliberately swallows exceptions and logs them so it can be run as a resilient background task.
    """
    import time
    from open_webui.models.billing import reconcile_pending_purchases

    while True:
        try:
            log.info("Reconcile loop tick: calling reconcile_pending_purchases")
            results = reconcile_pending_purchases(interval_seconds)
            log.info("Reconcile results: %s", results)
        except Exception:
            log.exception("Error during reconcile loop")
        # Wait with cancellation support
        try:
            await asyncio.wait_for(asyncio.sleep(interval_seconds), timeout=interval_seconds + 1)
        except asyncio.CancelledError:
            log.info("Reconcile loop cancelled during sleep")
            break
        # If a stop_event is provided and set, break
        if stop_event and stop_event.is_set():
            log.info("Reconcile loop stopping due to stop_event")
            break


async def run_once_now():
    """Run a single reconcile pass synchronously (for tests or on-demand use)."""
    from open_webui.models.billing import reconcile_pending_purchases

    log.info("Running one-time reconciliation")
    return reconcile_pending_purchases(0)


def start_background_reconcile(app, interval_seconds: int):
    """Start background reconcile task and store reference on app.state.

    If one already exists, it will not start a duplicate.
    """
    if getattr(app.state, "reconcile_task", None):
        log.info("Reconcile background task already running")
        return

    stop_event = asyncio.Event()
    task = asyncio.create_task(reconcile_loop(interval_seconds, stop_event))
    app.state.reconcile_task = task
    app.state.reconcile_stop_event = stop_event
    log.info("Started reconcile background task (interval=%s) PID=%s", interval_seconds, id(task))


async def stop_background_reconcile(app):
    task = getattr(app.state, "reconcile_task", None)
    stop_event = getattr(app.state, "reconcile_stop_event", None)
    if not task:
        return
    log.info("Stopping reconcile background task")
    if stop_event:
        stop_event.set()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    finally:
        app.state.reconcile_task = None
        app.state.reconcile_stop_event = None
        log.info("Reconcile background task stopped")

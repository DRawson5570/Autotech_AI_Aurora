import asyncio
import importlib


def test_run_once_now(monkeypatch):
    billing = importlib.import_module('open_webui.models.billing')
    called = {}

    def fake_reconcile(age):
        called['age'] = age
        return [{'purchase_id': 'p1', 'action': 'none'}]

    monkeypatch.setattr(billing, 'reconcile_pending_purchases', fake_reconcile)

    # call run_once_now from tasks
    tasks = importlib.import_module('open_webui.tasks.reconcile')
    res = asyncio.get_event_loop().run_until_complete(tasks.run_once_now())
    assert isinstance(res, list)
    assert called['age'] == 0


def test_background_reconcile_runs_once_and_stops(monkeypatch):
    billing = importlib.import_module('open_webui.models.billing')

    called = {'count': 0}

    def fake_reconcile(age):
        called['count'] += 1
        return [{'purchase_id': 'p1', 'action': 'none'}]

    monkeypatch.setattr(billing, 'reconcile_pending_purchases', fake_reconcile)

    tasks = importlib.import_module('open_webui.tasks.reconcile')

    # Run the loop for a short interval and cancel
    async def runner():
        stop_event = asyncio.Event()
        coro = asyncio.create_task(tasks.reconcile_loop(1, stop_event))
        # Wait until it runs once
        await asyncio.sleep(1.2)
        stop_event.set()
        await asyncio.wait_for(coro, timeout=2)
        return called['count']

    cnt = asyncio.get_event_loop().run_until_complete(runner())
    assert cnt >= 1

"""
Tests AlertConsumer — routing WebSocket par rôle.

Vérifie que chaque rôle rejoint le bon groupe de channel,
et que les alertes arrivent sur le bon groupe.
"""
import json
import pytest
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from channels.auth import AuthMiddlewareStack

from apps.biometric.consumers import AlertConsumer


def _make_application(user):
    """
    Construit une application ASGI qui injecte user + role dans le scope.
    Channels 4.x : WebsocketCommunicator prend (application, path) sans scope=kwarg.
    On wrap le consumer dans un middleware maison qui injecte le user.
    """
    try:
        role = user.profile.role
    except Exception:
        role = ''

    class _InjectUserMiddleware:
        def __init__(self, inner):
            self.inner = inner

        async def __call__(self, scope, receive, send):
            scope = {**scope, 'user': user, 'role': role}
            return await self.inner(scope, receive, send)

    return _InjectUserMiddleware(AlertConsumer.as_asgi())


def _make_anon_application():
    from django.contrib.auth.models import AnonymousUser

    class _AnonMiddleware:
        def __init__(self, inner):
            self.inner = inner

        async def __call__(self, scope, receive, send):
            scope = {**scope, 'user': AnonymousUser(), 'role': ''}
            return await self.inner(scope, receive, send)

    return _AnonMiddleware(AlertConsumer.as_asgi())


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_admin_joins_security_dashboard(admin_user):
    app = _make_application(admin_user)
    comm = WebsocketCommunicator(app, '/ws/alerts/')
    connected, _ = await comm.connect()
    assert connected
    msg = json.loads(await comm.receive_from())
    assert msg['type'] == 'CONNECTED'
    assert msg['group'] == 'security_dashboard'
    await comm.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_watchlist_admin_joins_security_dashboard(watchlist_admin_user):
    app = _make_application(watchlist_admin_user)
    comm = WebsocketCommunicator(app, '/ws/alerts/')
    connected, _ = await comm.connect()
    assert connected
    msg = json.loads(await comm.receive_from())
    assert msg['group'] == 'security_dashboard'
    await comm.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_border_joins_military_dashboard(border_user):
    app = _make_application(border_user)
    comm = WebsocketCommunicator(app, '/ws/alerts/')
    connected, _ = await comm.connect()
    assert connected
    msg = json.loads(await comm.receive_from())
    assert msg['group'] == 'military_dashboard'
    await comm.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_bank_joins_personal_group(bank_user):
    """BANK n'est ni admin ni frontière → groupe privé alerts_<id>."""
    app = _make_application(bank_user)
    comm = WebsocketCommunicator(app, '/ws/alerts/')
    connected, _ = await comm.connect()
    assert connected
    msg = json.loads(await comm.receive_from())
    assert msg['group'] == f'alerts_{bank_user.pk}'
    await comm.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_police_joins_personal_group(police_user):
    app = _make_application(police_user)
    comm = WebsocketCommunicator(app, '/ws/alerts/')
    connected, _ = await comm.connect()
    assert connected
    msg = json.loads(await comm.receive_from())
    assert msg['group'] == f'alerts_{police_user.pk}'
    await comm.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_unauthenticated_connection_rejected():
    app = _make_anon_application()
    comm = WebsocketCommunicator(app, '/ws/alerts/')
    connected, _ = await comm.connect()
    assert not connected


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_civil_alert_delivered_to_admin(admin_user):
    """Une alerte CIVIL doit arriver sur security_dashboard."""
    channel_layer = get_channel_layer()
    app = _make_application(admin_user)
    comm = WebsocketCommunicator(app, '/ws/alerts/')
    await comm.connect()
    await comm.receive_from()  # CONNECTED message

    await channel_layer.group_send('security_dashboard', {
        'type': 'watchlist_alert',
        'alert_level': 'ROUGE',
        'authority': 'CIVIL',
        'national_id': 'CG-KN-GBE-999001-T1',
        'reason': 'Test civil',
        'issued_by': 'PNC',
        'agent_id': None,
    })

    raw = await comm.receive_from()
    msg = json.loads(raw)
    assert msg['type'] == 'WATCHLIST_HIT'
    assert msg['alert_level'] == 'ROUGE'
    assert msg['authority'] == 'CIVIL'
    await comm.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_military_alert_delivered_to_border(border_user):
    """Une alerte MILITAIRE doit arriver sur military_dashboard."""
    channel_layer = get_channel_layer()
    app = _make_application(border_user)
    comm = WebsocketCommunicator(app, '/ws/alerts/')
    await comm.connect()
    await comm.receive_from()  # CONNECTED

    await channel_layer.group_send('military_dashboard', {
        'type': 'watchlist_alert',
        'alert_level': 'ROUGE',
        'authority': 'MILITAIRE',
        'national_id': 'CG-KN-GBE-999001-T1',
        'reason': 'Test militaire',
        'issued_by': 'FARDC',
        'agent_id': None,
    })

    raw = await comm.receive_from()
    msg = json.loads(raw)
    assert msg['type'] == 'WATCHLIST_HIT'
    assert msg['authority'] == 'MILITAIRE'
    await comm.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_bank_does_not_receive_civil_alert(bank_user):
    """BANK est dans alerts_<id>, pas security_dashboard → pas d'alerte CIVIL."""
    channel_layer = get_channel_layer()
    app = _make_application(bank_user)
    comm = WebsocketCommunicator(app, '/ws/alerts/')
    await comm.connect()
    await comm.receive_from()  # CONNECTED

    await channel_layer.group_send('security_dashboard', {
        'type': 'watchlist_alert',
        'alert_level': 'ROUGE',
        'authority': 'CIVIL',
        'national_id': 'CG-KN-GBE-999001-T1',
        'reason': 'Test isolation bank',
        'issued_by': 'PNC',
        'agent_id': None,
    })

    # BANK ne doit pas recevoir ce message
    assert await comm.receive_nothing(timeout=0.3), (
        "VIOLATION Silent Flagging: BANK a reçu une alerte watchlist CIVIL"
    )
    await comm.disconnect()

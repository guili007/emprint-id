import json
from channels.generic.websocket import AsyncWebsocketConsumer

ADMIN_ROLES = {'ROLE_ADMIN', 'ROLE_WATCHLIST_ADMIN'}
MILITARY_ROLES = {'ROLE_BORDER'}


class AlertConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer pour les alertes watchlist temps réel.

    Routing des groupes par rôle :
      ROLE_ADMIN / ROLE_WATCHLIST_ADMIN → security_dashboard  (alertes CIVIL + ETAT)
      ROLE_BORDER                       → military_dashboard   (alertes MILITAIRE + ETAT)
      Autres rôles terrain              → alerts_<user_id>     (usage futur)
    """

    async def connect(self):
        user = self.scope.get('user')
        if not user or not user.is_authenticated:
            await self.close()
            return

        role = self.scope.get('role', '') or getattr(user, 'role', '')

        if role in ADMIN_ROLES:
            self.group_name = 'security_dashboard'
        elif role in MILITARY_ROLES:
            self.group_name = 'military_dashboard'
        else:
            self.group_name = f'alerts_{user.pk}'

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send(text_data=json.dumps({'type': 'CONNECTED', 'group': self.group_name}))

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def watchlist_alert(self, event):
        """Reçu depuis _send_silent_alert via channel_layer.group_send."""
        await self.send(text_data=json.dumps({
            'type': 'WATCHLIST_HIT',
            'alert_level': event['alert_level'],
            'authority': event.get('authority', 'CIVIL'),
            'national_id': event['national_id'],
            'reason': event['reason'],
            'issued_by': event.get('issued_by', ''),
            'agent_id': event.get('agent_id'),
        }))

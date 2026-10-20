import json
from channels.generic.websocket import AsyncWebsocketConsumer

ADMIN_ROLES = {'ROLE_ADMIN', 'ROLE_WATCHLIST_ADMIN'}


class AlertConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer pour les alertes watchlist temps réel.

    Admins  → groupe "security_dashboard" (reçoivent tous les watchlist hits)
    Terrain → groupe "alerts_<user_id>"  (alertes personnelles, usage futur)
    """

    async def connect(self):
        user = self.scope.get('user')
        if not user or not user.is_authenticated:
            await self.close()
            return

        role = self.scope.get('role', '') or getattr(user, 'role', '')
        if role in ADMIN_ROLES:
            self.group_name = 'security_dashboard'
        else:
            self.group_name = f'alerts_{user.pk}'

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # Confirme la connexion au client
        await self.send(text_data=json.dumps({'type': 'CONNECTED', 'group': self.group_name}))

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def watchlist_alert(self, event):
        """Reçu depuis _send_silent_alert via channel_layer.group_send."""
        await self.send(text_data=json.dumps({
            'type': 'WATCHLIST_HIT',
            'alert_level': event['alert_level'],
            'national_id': event['national_id'],
            'reason': event['reason'],
            'issued_by': event.get('issued_by', ''),
            'agent_id': event.get('agent_id'),
        }))

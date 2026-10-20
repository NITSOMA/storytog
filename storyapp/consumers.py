import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger(__name__)

class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope.get('user')
        self.user_id = self.scope['url_route']['kwargs']['user_id']

        # Only the logged-in user may listen to their own notifications.
        if not user or not user.is_authenticated or str(user.id) != self.user_id:
            await self.close()
            return

        try:
            self.group_name = f"user_notifications_{self.user_id}"

            await self.channel_layer.group_add(
                self.group_name,
                self.channel_name
            )

            await self.accept()

        except Exception:
            logger.exception("Could not open notification socket for user %s", self.user_id)
            await self.close(code=1011)

    async def disconnect(self, close_code):
        try:
            if hasattr(self, 'group_name'):
                await self.channel_layer.group_discard(
                    self.group_name,
                    self.channel_name
                )

        except Exception:
            logger.exception("Error leaving notification group %s", self.group_name)

    async def send_notification(self, event):
        message = event['message']

        await self.send(text_data=json.dumps({
            'notification': message,
            'event_type': event.get('event_type', 'new_request')
        }))
import json
from channels.generic.websocket import AsyncWebsocketConsumer

class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        try:
           
            self.user_id = self.scope['url_route']['kwargs']['user_id']
            self.group_name = f"user_notifications_{self.user_id}"

            await self.channel_layer.group_add(
                self.group_name,
                self.channel_name
            )

            await self.accept()
           
            
        except Exception as e:
            
            await self.close(code=1011)

    async def disconnect(self, close_code):
        try:
            if hasattr(self, 'group_name'):
                await self.channel_layer.group_discard(
                    self.group_name,
                    self.channel_name
                )
           
        except Exception as e:
            print(f" Error during disconnect: {str(e)}")

    async def send_notification(self, event):
        message = event['message']
        await self.send(text_data=json.dumps({
            'notification': message
        }))
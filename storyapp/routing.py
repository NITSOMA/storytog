from django.urls import path
from . import consumers

websocket_urlpatterns = [
   
    path('ws/notifications/<str:user_id>/', consumers.NotificationConsumer.as_asgi()),
]
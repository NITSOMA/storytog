

import os

from django.core.asgi import get_asgi_application
from channels.auth import AuthMiddlewareStack

from channels.routing import ProtocolTypeRouter, URLRouter
import storyapp.routing

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'writespace.settings')

application = ProtocolTypeRouter({
   
    "http": get_asgi_application(),
    "websocket":AuthMiddlewareStack(          # <-- 2. WRAP YOUR ROUTER HERE
        URLRouter(
            storyapp.routing.websocket_urlpatterns
        )
    ),
})



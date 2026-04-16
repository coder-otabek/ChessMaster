import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
import chess.routing
import chat.routing

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chessmaster.settings')

application = ProtocolTypeRouter({
    'http': get_asgi_application(),
    'websocket': AuthMiddlewareStack(
        URLRouter(
            chess.routing.websocket_urlpatterns +
            chat.routing.websocket_urlpatterns
        )
    ),
})

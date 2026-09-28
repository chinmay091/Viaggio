import os
import sys
from pathlib import Path
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

base_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(base_dir / "apps"))
sys.path.insert(0, str(base_dir))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

# Initialize Django ASGI application early to ensure the AppRegistry
# is populated before importing code that may import ORM models.
django_asgi_app = get_asgi_application()

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        # WebSocket routing will be extended in Phase 6/12
        "websocket": AuthMiddlewareStack(
            URLRouter([])
        ),
    }
)

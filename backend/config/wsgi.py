import os
import sys
from pathlib import Path
from django.core.wsgi import get_wsgi_application

base_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(base_dir / "apps"))
sys.path.insert(0, str(base_dir))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

application = get_wsgi_application()

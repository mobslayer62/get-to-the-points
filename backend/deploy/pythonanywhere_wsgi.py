# Template for the WSGI file on PythonAnywhere.
#
# Copy everything below into the WSGI configuration file linked on the
# PythonAnywhere "Web" tab, then:
#   1. replace USERNAME (3 places) with your PythonAnywhere username
#   2. replace the secret key with a long random string, e.g. from
#        python -c "import secrets; print(secrets.token_urlsafe(50))"
# Never commit the real secret key to GitHub.

import os
import sys

path = "/home/USERNAME/get-to-the-points/backend"
if path not in sys.path:
    sys.path.insert(0, path)

os.environ["DJANGO_SETTINGS_MODULE"] = "Mainprogram.settings"
os.environ["DJANGO_DEBUG"] = "0"
os.environ["DJANGO_ALLOWED_HOSTS"] = "USERNAME.pythonanywhere.com"
os.environ["DJANGO_SECRET_KEY"] = "PASTE-A-LONG-RANDOM-STRING-HERE"

from django.core.wsgi import get_wsgi_application  # noqa: E402

application = get_wsgi_application()

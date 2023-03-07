from .base import *

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = "django-insecure-&%))u!78ouln2w+t$^14r55oa88k-wm0)7k)i!-0$+d5)40*k9"

# SECURITY WARNING: define the correct hosts in production!
ALLOWED_HOSTS = ["8000",'localhost']

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

CSRF_TRUSTED_ORIGINS = ['https://8000-sdivyanshu90-wagtail-zz7jqlv1uio.ws-us89b.gitpod.io']

try:
    from .local import *
except ImportError:
    pass

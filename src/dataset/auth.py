from django.conf import settings
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User
import logging, requests


access_logger = logging.getLogger('motiondb_access')
logger = logging.getLogger(__name__)

# TODO: Using PyOpenSSL is necessary to work around problems in ssl module of Python < 2.7.9. Later, this can be removed again.
#       (see https://urllib3.readthedocs.org/en/latest/security.html#insecureplatformwarning)
import urllib3.contrib.pyopenssl
urllib3.contrib.pyopenssl.inject_into_urllib3()

class RedmineBackend(ModelBackend):
    def authenticate(self, username=None, password=None):
        if not username or not password:
            return None

        access_logger.debug('Attempting Redmine login for username "%s"...' % username)
        result = requests.get(settings.REDMINE_AUTH_REST_URL, auth=(username, password), verify=True)

        try:
            json_data = result.json()
        except ValueError:
            return None

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            # Create local user if it does not exist
            user = User(username=username)
            user.set_unusable_password()
            user.save()

            logger.debug('Created new Django user with locked password for username "%s".' % username)

        return user


class EmailBackend(ModelBackend):
    def authenticate(self, username=None, password=None):
        if not username or not password:
            return None
        try:
            user = User.objects.get(email=username)
            if user.check_password(password):
                return user
        except User.DoesNotExist:
            return None
        return None

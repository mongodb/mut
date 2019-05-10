import configparser
import logging
import os
import pwd
from pathlib import Path

DEFAULT_CONFIG_PATH = Path('~/.config/giza-aws-authentication.conf').expanduser()
SAMPLE_CONFIG = '''[authentication]
accesskey=<AWS access key>
secretkey=<AWS secret key>
'''

logger = logging.getLogger(__name__)


def create_config_framework(path: Path) -> None:
    """Create a skeleton configuration file with appropriately locked-down
       permissions."""
    try:
        os.mkdir(os.path.dirname(path), 0o751)
    except OSError:
        pass

    # Make sure we don't write the framework if it already exists.
    try:
        with os.fdopen(os.open(path,
                               os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                               0o600), 'x') as conf_file:
            conf_file.write('[authentication]\n')
    except IOError:
        pass


class AuthenticationInfo:
    """Stores S3 authentication information."""
    def __init__(self, access_key: str, secret_key: str, username: str) -> None:
        self.access_key = access_key
        self.secret_key = secret_key
        self.username = username

    @classmethod
    def load(cls, path: Path = DEFAULT_CONFIG_PATH) -> 'AuthenticationInfo':
        """Returns an AuthenticationInfo instance giving any necessary S3 login
           information."""
        access_key = os.environ.get('AWS_ACCESS_KEY_ID', None)
        secret_key = os.environ.get('AWS_SECRET_ACCESS_KEY', None)
        username = os.environ.get('STAGING_USERNAME', None)

        cfg = configparser.ConfigParser()
        cfg.read(path)

        # Load S3 authentication information
        try:
            if not access_key:
                access_key = cfg.get('authentication', 'accesskey')

            if not secret_key:
                secret_key = cfg.get('authentication', 'secretkey')
        except (configparser.NoSectionError, configparser.NoOptionError):
            print('No staging authentication found. Create a file at {0} with '
                  'contents like the following:\n'.format(path))
            print(SAMPLE_CONFIG)
            create_config_framework(path)
            raise ValueError('Missing authentication information')

        # Get the user's preferred name; we use this as part of our S3 namespaces
        if not username:
            try:
                username = cfg.get('personal', 'username')
            except (configparser.NoSectionError, configparser.NoOptionError):
                username = pwd.getpwuid(os.getuid()).pw_name

        logger.info('Authentication: access_key="%s", username="%s"', access_key, username)
        return AuthenticationInfo(access_key, secret_key, username)

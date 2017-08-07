import configparser
import logging
import os
import pwd
import stat

CONFIG_PATH = '~/.config/giza-aws-authentication.conf'
SAMPLE_CONFIG = '''[authentication]
accesskey=<AWS access key>
secretkey=<AWS secret key>
'''

logger = logging.getLogger(__name__)


def create_config_framework(path: str) -> None:
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
    def load(cls) -> 'AuthenticationInfo':
        """Returns an AuthenticationInfo instance giving any necessary S3 login
           information."""
        cfg_path = os.path.expanduser(CONFIG_PATH)
        cfg = configparser.ConfigParser()
        cfg.read(cfg_path)

        # Warn the user if config permissions are too lax
        try:
            if os.name == 'posix' and stat.S_IMODE(os.stat(cfg_path).st_mode) != 0o600:
                logger.warn('Your AWS authentication file is poorly protected! You should run')
                logger.warn('    chmod 600 %s', cfg_path)
        except OSError:
            pass

        # Load S3 authentication information
        try:
            access_key = cfg.get('authentication', 'accesskey')
            secret_key = cfg.get('authentication', 'secretkey')
        except (configparser.NoSectionError, configparser.NoOptionError):
            print('No staging authentication found. Create a file at {0} with '
                  'contents like the following:\n'.format(cfg_path))
            print(SAMPLE_CONFIG)
            create_config_framework(cfg_path)
            raise ValueError('Missing authentication information')

        # Get the user's preferred name; we use this as part of our S3 namespaces
        try:
            username = cfg.get('personal', 'username')
        except (configparser.NoSectionError, configparser.NoOptionError):
            username = pwd.getpwuid(os.getuid()).pw_name

        return AuthenticationInfo(access_key, secret_key, username)

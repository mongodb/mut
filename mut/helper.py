"""
Usage: mut convert-redirects [...]
       mut images [...]
       mut intersphinx [...]
       mut publish [...]
       mut index [...]
"""

import os.path
import subprocess
import sys


def main() -> None:
    """Main program entry point."""
    us = os.path.dirname(sys.argv[0])
    try:
        subprocess.call([os.path.join(us, 'mut-{}'.format(sys.argv[1])),
                         *sys.argv[2:]])
    except (IndexError, FileNotFoundError):
        print(__doc__.strip())
        sys.exit(1)


if __name__ == '__main__':
    main()

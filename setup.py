import sys
from setuptools import setup, find_packages
import mut

REQUIRES = [
    'boto3',
    'certifi',
    'cssselect',
    'docopt',
    'html5-parser',
    'lxml',
    'PyYAML',
    'requests',
    'rstcloth>=0.2.6'
]

# Need a fallback for the typing module
if sys.version < '3.5':
    REQUIRES.append('mypy')

setup(
    name='mut',
    description='',
    version=mut.__version__,
    author='Andrew Aldridge',
    author_email='i80and@foxquill.com',
    license='Apache',
    packages=find_packages(),
    install_requires=REQUIRES,
    classifiers=[
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: Apache Software License',
        'Topic :: Software Development :: Build Tools',
        'Topic :: Documentation',
        'Topic :: Text Processing',
        ],
    entry_points={
        'console_scripts': [
            'mut = mut.helper:main',
            'mut-convert-redirects = mut.convert_redirects:main',
            'mut-images = mut.build_images:main',
            'mut-index = mut.index.main:main',
            'mut-intersphinx = mut.intersphinx:main',
            'mut-publish = mut.stage:main',
            'mut-redirects = mut.redirects.redirect_main:main',
            ],
        }
    )

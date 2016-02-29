from setuptools import setup

REQUIRES = [
    'docopt~=0.6',
    'docutils',
    'PyYAML',
    'rstcloth>0.2.5',
    'libgiza==0.2.13'
]

setup(
    name='mut',
    description='',
    version='0.0.0',
    author='Andrew Aldridge',
    author_email='i80and@foxquill.com',
    license='Apache',
    packages=['mut'],
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
            'mut-build = mut.main:main',
            'mut-stage = mut.stage:main',
            'mut-publish = mut.stage:main'
            ],
        }
    )

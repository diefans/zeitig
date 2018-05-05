"""package setup"""

import os

from setuptools import find_packages, setup

__version__ = '0.2.3'


def read(*paths):
    """Build a file path from *paths* and return the contents."""
    with open(os.path.join(*paths), 'r') as f:
        return f.read()


setup(
    name="zeitig",
    author="Oliver Berger",
    author_email="diefans@gmail.com",
    url="https://github.com/diefans/zeitig",
    description='time tracker.',
    long_description=read('README.rst'),
    version=__version__,
    classifiers=[
        'Development Status :: 4 - Beta',
        'License :: OSI Approved :: Apache Software License',
        'Intended Audience :: Developers',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
    ],
    license='Apache License Version 2.0',

    keywords="time tracker",

    package_dir={'': 'src'},
    packages=find_packages(
        'src',
        exclude=["tests*"]
    ),
    include_package_data=True,
    entry_points={
        'console_scripts': [
            'z=zeitig.scripts:run'
        ],
    },

    install_requires=read('requirements.txt').split('\n'),
    extras_require={
        'dev': read('requirements-dev.txt').split('\n'),
    },
    dependency_links=[
    ],
)

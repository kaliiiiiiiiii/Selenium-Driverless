# Always prefer setuptools over distutils
from setuptools import setup, find_packages

from os import path

here = path.abspath(path.dirname(__file__))


def readme():
    try:
        with open('README.rst') as f:
            return f.read()
    except FileNotFoundError:
        return ""

setup(
    name='chromewhip',

    version='0.3.4',

    description='asyncio driver + HTTP server for Chrome devtools protocol',
    long_description=readme(),
    # The project's main homepage.
    url='https://github.com/chuckus/chromewhip',
    download_url='https://github.com/chuckus/chromewhip/archive/v0.3.4.tar.gz',

    # Author details
    author='Charlie Smith',
    author_email='charlie@chuckus.nz',

    # Choose your license
    license='MIT',

    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        'Development Status :: 3 - Alpha',

        'Intended Audience :: Developers',
        'Topic :: Software Development :: Build Tools',

        'License :: OSI Approved :: MIT License',

        'Programming Language :: Python :: 3.7',
    ],

    # What does your project relate to?
    keywords='scraping chrome scraper browser automation',

    # You can just specify the packages manually here if your project is
    # simple. Or you can use find_packages().
    packages=find_packages(exclude=['contrib', 'docs', 'tests']),

    # Alternatively, if you want to distribute just a my_module.py, uncomment
    # this:
    #   py_modules=["my_module"],

    # List run-time dependencies here.  These will be installed by pip when
    # your project is installed. For an analysis of "install_requires" vs pip's
    # requirements files see:
    # https://packaging.python.org/en/latest/requirements.html
    install_requires=[
        'aiohttp==3.6.2', 'websockets==7.0', 'beautifulsoup4==4.7.1', 'lxml==4.6.2',
        'pyyaml==5.1', 'Pillow==7.1.0'
    ],

    # List additional groups of dependencies here (e.g. development
    # dependencies). You can install these using the following syntax,
    # for example:
    # $ pip install -e .[dev,test]
    extras_require={
        'dev': ['Jinja2==2.10.1', 'jsonpatch==1.23'],
        'test': ['pytest-asyncio==0.10.0'],
    },

    # To provide executable scripts, use entry points in preference to the
    # "scripts" keyword. Entry points provide cross-platform support and allow
    # pip to create the appropriate form of executable for the target platform.
    entry_points={
        'console_scripts': [
            'chromewhip=chromewhip:main',
        ],
    },
)

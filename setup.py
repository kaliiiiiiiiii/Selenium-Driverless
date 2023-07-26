import setuptools

requirements = ['selenium~=4.6']

# pycdp-requirements
requirements.extend([
    "aiohttp~=3.8.5",
    "aiosignal~=1.3.1",
    "async-timeout~=4.0.2",
    "attrs~=23.1.0",
    "charset-normalizer~=3.2.0",
    "deprecated~=1.2.14",
    "frozenlist~=1.4.0",
    "idna~=3.4",
    "inflection~=0.5.1",
    "multidict~=6.0.4",
    "wrapt~=1.15.0",
    "yarl~=1.9.2",
])

with open('README.md', 'r', encoding='utf-8') as fh:
    long_description = fh.read()

setuptools.setup(
    name='selenium_driverless',
    author='Aurin Aegerter',
    author_email='aurinliun@gmx.ch',
    description='Undetected selenium without chromedriver usage',
    keywords='Selenium, webautomation',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/kaliiiiiiiiii/Selenium-Driverless',
    project_urls={
        'Documentation': 'https://github.com/kaliiiiiiiiii/Selenium-Driverless',
        'Bug Reports':
            'https://github.com/kaliiiiiiiiii/Selenium-Driverless/issues',
        'Source Code': 'https://github.com/kaliiiiiiiiii/Selenium-Driverless',
    },
    package_dir={'': 'src'},
    packages=setuptools.find_packages(where='src'),
    classifiers=[
        # see https://pypi.org/classifiers/
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'License :: Free for non-commercial use',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Topic :: Internet :: Proxy Servers',
        'Topic :: Internet',
        'Topic :: Internet :: WWW/HTTP :: Browsers',

    ],
    python_requires='>=3.8',
    install_requires=requirements,
    include_package_data=True,
    extras_require={
        'dev': ['check-manifest'],
        # 'test': ['coverage'],
    },
)

import sys
import setuptools

print('This package has a "Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0)" Licence.\n'
      "therefore, you'll have to ask the developer first, if you want to use this package for your buisiness.\n"
      "https://github.com/kaliiiiiiiiii/Selenium-Driverless", file=sys.stderr)

requirements = ['selenium~=4.6', "cdp-socket>=1.1", "numpy~=1.21", "matplotlib~=3.5", "scipy~=1.7"]

with open('README.md', 'r', encoding='utf-8') as fh:
    long_description = fh.read()

setuptools.setup(
    name='selenium_driverless',
    author='Aurin Aegerter',
    author_email='aurinliun@gmx.ch',
    description='Undetected selenium without chromedriver usage (Non-commercial use only!)',
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
    python_requires='>=3.7',
    install_requires=requirements,
    include_package_data=True,
    extras_require={
        'dev': ['check-manifest'],
        # 'test': ['coverage'],
    },
    license='CC BY-NC-SA 4.0'
)

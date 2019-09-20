"""
Copyright (c) 2019
Harvard FAS Informatics
All rights reserved.

@author: Aaron Kitzmiller
"""
import os
import re
from setuptools import setup, find_packages

def getVersion():
    version = '0.0.0'
    with open('p3/apps/__init__.py','r') as f:
        contents = f.read().strip()

    m = re.search(r"__version__ = '([\d\.]+)'", contents)
    if m:
        version = m.group(1)
    return version

setup(
    name = "moduleQuery",
    version = getVersion(),
    author='Aaron Kitzmiller <aaron_kitzmiller@harvard.edu>',
    author_email='aaron_kitzmiller@harvard.edu',
    description='Command line application query tool.  Should work for both Python 2 and 3',
    license='LICENSE.txt',
    keywords = "executables",
    url='http://github/harvardinformatics/moduleQuery/',
    packages = find_packages(),
    long_description=open('README.md').read(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Topic :: Utilities",
    ],
    entry_points={
        'console_scripts': [
            'module-query=p3.apps.moduleQuery:main',
            'check-activation=p3.apps.checkActivation:main',
        ]
    },
    install_requires = [
        'mysqlclient',
    ],
)

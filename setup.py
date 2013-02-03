#!/usr/bin/env python

import os
from distutils.core import setup

def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(
    name='locket',
    version='0.1.1',
    description='File-based locks for Python for Linux and Windows',
    long_description=read("README"),
    author='Michael Williamson',
    url='http://github.com/mwilliamson/locket.py',
    packages=['locket'],
    keywords="lock filelock lockfile"
)

#!/usr/bin/env python

# Use setuptools, if available.  Otherwise, fall back to distutils.
try:
    from setuptools import setup
except ImportError:
    import sys
    sys.stderr.write("warning: Proceeding without setuptools\n")
    from distutils.core import setup

setup(
    name='f469kernel',
    py_modules=['f469kernel'],
    version="0.1.0",
    description='Jupyter Notebook Micropython kernel',
    author='Stepan Snigirev',
    author_email='snigire.stepan@gmail.com',
    url='https://github.com/diybitcoinhardware/f469-disco',
    long_description="""\
This module interacts with micropython binary process or micropython board i.e. f469 discovery, pyboard or esp32.
""")
#!/usr/bin/env python
from setuptools import setup

from boom import __version__ as boom_version

setup(
    name='boom',
    version=boom_version,
    description=("""The Boom Boot Manager."""),
    author='Bryn M. Reeves',
    author_email='bmr@redhat.com',
    url='https://github.com/bmr-cymru/boom',
    license="GPLv2",
    test_suite="tests",
    scripts=['bin/boom'],
    packages=['boom'],
)


# vim: set et ts=4 sw=4 :

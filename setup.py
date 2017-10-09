#!/usr/bin/env python
from setuptools import setup

setup(
    name='boom',
    version="0.1",
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

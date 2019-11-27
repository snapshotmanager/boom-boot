# Copyright (C) 2017 Red Hat, Inc., Bryn M. Reeves <bmr@redhat.com>
#
# boom/__init__.py - Boom package initialisation
#
# This file is part of the boom project.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions
# of the GNU General Public License v.2.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA
"""This module provides classes and functions for creating, displaying,
and manipulating boot loader entries complying with the Boot Loader
Specification.

The ``boom`` package contains global definitions, functions to configure
the Boom environment, logging infrastructure for the package and a
``Selection`` class used to select one or more ``OsProfile``,
``HostProfile``, ``BootEntry``, or ``BootParams`` object according to
specified selection criteria.

Individual sub-modules provide interfaces to the various components of
Boom: operating system and host profiles, boot loader entries and boot
parameters, the boom CLI and procedural API and a simple reporting
module to produce tabular reports on Boom objects.

See the sub-module documentation for specific information on the
classes and interfaces provided, and the ``boom`` tool help output and
manual page for information on using the command line interface.
"""
from __future__ import print_function

from ._boom import *
from ._boom import __all__

__version__ = "1.0"

# vim: set et ts=4 sw=4 :

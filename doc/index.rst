Boom documentation
==================

Boom is a boot manager for Linux systems using the
`BootLoader Specification <https://systemd.io/BOOT_LOADER_SPECIFICATION>`_.
Boom can create and remove boot entries for the system, or for
snapshots of the system using LVM2, or BTRFS.

Boom is tested with grub2 and the Red Hat BLS patch but the boot
entries written by boom should be usable with any bootloader that
implements the BLS (for e.g. `systemd-boot <https://www.freedesktop.org/wiki/Software/systemd/systemd-boot/>`_).

Contents:

.. toctree::
   :maxdepth: 2

   boom
   modules


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`


Boom documentation
==================

Boom is a boot manager for Linux systems using the
`Boot Loader Specification
<https://uapi-group.org/specifications/specs/boot_loader_specification/>`_.
Boom can create and remove boot entries for the system, or for
snapshots of the system using LVM2, Stratis, or BTRFS.

Boom is tested with grub2 and the Red Hat BLS patch but the boot
entries written by boom should be usable with any bootloader that
implements the BLS (for e.g. `systemd-boot <https://www.freedesktop.org/wiki/Software/systemd/systemd-boot/>`_).

Contents:

.. toctree::
   :maxdepth: 2
   :caption: Documentation

   user_guide
   boom
   modules


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`


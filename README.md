# Boom

Boom is a *boot manager* for Linux systems using boot loaders that support
the [BootLoader Specification][0] for boot entry configuration. It is
based on the boot manager design discussed in the
[Boot-to-snapshot design v0.6][1] document.

Boom aims to be a simple and extensible, and to be able to create boot
configurations for a wide range of Linux system configurations and boot
parameters.

This project is hosted at:

  * http://github.com/bmr-cymru/boom

For the latest version, to contribute, and for more information, please visit
the project pages or join the mailing list.

To clone the current master (development) branch run:

```
git clone git://github.com/bmr-cymru/boom.git
```
## Reporting bugs

Please report bugs via the mailing list or by opening an issue in the [GitHub
Issue Tracker][2]

## Mailing list

The [dm-devel][3] is the mailing list for any boom-related questions and
discussion. Patch submissions and reviews are welcome too.

## Patches and pull requests

Patches can be submitted via the mailing list or as GitHub pull requests. If
using GitHub please make sure your branch applies to the current master as a
'fast forward' merge (i.e. without creating a merge commit). Use the `git
rebase` command to update your branch to the current master if necessary.

## Documentation

API [documentation][4] is automatically generated using [Sphinx][5]
and [Read the Docs][6].

Installation and user documentation will be added in a future update.

 [0]: https://www.freedesktop.org/wiki/Specifications/BootLoaderSpec/
 [1]: https://github.com/bmr-cymru/snapshot-boot-docs
 [2]: https://github.com/bmr-cymru/boom/issues
 [3]: https://www.redhat.com/mailman/listinfo/dm-devel
 [4]: https://boom.readthedocs.org/en/latest/index.html#
 [5]: http://sphinx-doc.org/
 [6]: https://www.readthedocs.org/

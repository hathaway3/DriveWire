# Client (CoCo) Side Software (ROMs, Cassette Images, etc.)

## Simple Start

Please visit Cloud 9's DriveWire page:
[http://cloud9tech.com/Cloud-9/Support/DriveWire%203%20User%20Manual.pdf](http://cloud9tech.com/Cloud-9/Support/DriveWire%203%20User%20Manual.pdf)

Here you will find detailed instructions and related downloads for various ways to make your CoCo talk to a DriveWire server.

!!! note "Generalization (Review Needed)"
    The following instruction has been generalized as the configuration is common across DriveWire server implementations (Java, MicroPython, etc.).

    > Instructions for DriveWire 3 are generally applicable to modern DriveWire servers for all aspects of CoCo side configuration.

## A Tale of Too Many ROMs

!!! note "Generalization (Review Needed)"
    Simplified ROM and server terminology.

    Cloud 9 never released a "DriveWire 4" ROM. Modern DriveWire servers are designed to work with the Cloud 9 ROM labeled "DriveWire 3". Current servers are completely compatible replacements for the legacy DriveWire 3 server and do not require any changes on the CoCo side from a DriveWire 3 configuration.

!!! note "Generalization (Review Needed)"
    Generalized "DW4" references to "current DriveWire protocols".

    However, since the original DriveWire protocols were created, Darren Atkinson (master hacker who created the serial routines in DW3) has developed an even better serial technique. This technique allows 230Kbps on a Coco 3 and 115.2K on a Coco 2 or Dragon. These new routines can be found in ROMs and OS9 drivers labeled "DW4" (referencing the protocol version), and they will only work with a compatible DriveWire server. This was not meant to imply they are required by all users. _A DW3 ROM will work absolutely fine with modern DriveWire servers._ A ROM using the newer "DW4" protocol will not work with a legacy DW3 server.

!!! note "Generalization (Review Needed)"
    Generalized Becker/DW4 ROM info.

    You may also find ROMs and disks labeled "becker" or referring to the Becker interface. Like the improved serial "DW4" protocol ROMs, these will only work with a modern DriveWire server. Unlike the "DW4" ROMS, these are not intended for use on any traditional CoCo. Instead, these are for use in emulators (VCC and XRoar support the Becker interface) or the CoCo3FPGA board, or possibly other places where using a traditional physical bitbanging serial interface isn't ideal and/or possible.

!!! note "Generalization (Review Needed)"
    Generalized legacy vs modern server comparison.

    Yet another ROM variant is the "DW3DOS" family. These *are* released by Cloud 9 and *do* work fine with legacy DriveWire 3 servers (and, of course, current DriveWire servers). Unlike the other ROMs mentioned here, these ROMs do not contain a variant of BASIC called HDBDOS. Instead these ROMs are designed to automatically load an OS9 style boot track at power on. Essentially these ROMS do a "DOS" command at boot time, so try to have a bootable disk mounted in your DriveWire server when you turn on a Coco using these ROMs.

## Summary

**If you are new to DriveWire, please use the software and instructions on the Cloud 9 site linked above.**

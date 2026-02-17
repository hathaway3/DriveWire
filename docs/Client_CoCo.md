# Client (CoCo) Side Software (ROMs, Cassette Images, etc.)

## Simple Start

Please visit Cloud 9's DriveWire page:
[http://cloud9tech.com/Cloud-9/Support/DriveWire%203%20User%20Manual.pdf](http://cloud9tech.com/Cloud-9/Support/DriveWire%203%20User%20Manual.pdf)

Here you will find detailed instructions and related downloads for various ways to make your CoCo talk to a DriveWire server.

> [!NOTE]
> Instructions for DriveWire 3 are applicable to DriveWire 4 for all aspects of CoCo side configuration.

## A Tale of Too Many ROMs

Cloud 9 never released a "DriveWire 4" ROM. The DriveWire 4 server is designed to work with the Cloud 9 ROM labeled "DriveWire 3". The DriveWire 4 server is a completely compatible replacement for the DriveWire 3 server and does not require any changes on the CoCo side from a DriveWire 3 configuration.

However, in the time since the DW4 server was created, Darren Atkinson (master hacker who created the serial routines in DW3) has developed an even better serial technique. This technique allows 230Kbps on a Coco 3 and 115.2K on a Coco 2 or Dragon. These new routines can be found in ROMs and OS9 drivers labeled "DW4", and they will only work with a DriveWire 4 server. This was not meant to imply they are required by users of the DW4 server. _A DW3 ROM will work absolutely fine with DW4 server._ A DW4 ROM will not work fine with a DW3 server.

You may also find ROMs and disks labeled "becker" or referring to the Becker interface. Like the improved serial "DW4" ROMs, these will only work with a DriveWire 4 server. Unlike the "DW4" ROMS, these are not intended for use on any traditional CoCo. Instead, these are for use in emulators (VCC and XRoar support the Becker interface) or the CoCo3FPGA board, or possibly other places where using a traditional physical bitbanging serial interface isn't ideal and/or possible.

Yet another ROM variant is the "DW3DOS" family. These *are* released by Cloud 9 and *do* work fine with DriveWire 3 servers (and, of course, DW4 servers). Unlike the other ROMs mentioned here, these ROMs do not contain a variant of BASIC called HDBDOS. Instead these ROMs are designed to automatically load an OS9 style boot track at power on. Essentially these ROMS do a "DOS" command at boot time, so try to have a bootable disk mounted in your DriveWire server when you turn on a Coco using these ROMs.

## Summary

**If you are new to DriveWire, please use the software and instructions on the Cloud 9 site linked above.**

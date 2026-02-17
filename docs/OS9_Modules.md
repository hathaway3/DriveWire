# OS-9 Modules

## Intro

If you'd like to add DriveWire functionality to your existing OS-9 system, you'll need to load various modules depending on which features you'd like to use.

Premade NitrOS-9 boot disks with all the modules included are available from the [NitrOS-9 project](http://www.nitros9.org/latest/).

The DriveWire modules are included in the NitrOS-9 source code if you'd like to build them yourself.
For specific details on NitrOS-9 Level 2 integration, please see [NitrOS9 Level 2 Integration](NitrOS9_Level2_Integration.md).

## Modules

### Base I/O

The I/O routines for all DriveWire functionality are contained in the dwio module. The stock dwio module is called **dwio.sb**. This module uses the bit banger for it's I/O. You can use alternate dwio modules if you'd like to use another device. In the NitrOS9 CVS you will find dw3_becker.sb which enables high speed functionality in Gary Becker's Coco3FPGA project, and dw3_mess.sb which is used with John Linville's MESS patch. 

!!! note "Generalization (Review Needed)"
    The following TODO has been generalized to refer to enhanced serial protocols rather than just "DW4".

    TODO - find the dwsub for 6551 TODO - document enhanced "Turbo" I/O protocols.

You must load one dwio module in order to use any DriveWire functionality. 

### Disk Devices

The driver for RBF disk devices is **rbdw.dr**

This module is required if you'd like to access disk images as RBF devices. You must also load one or more device descriptors corresponding to the drives you would like to have available. These are x0.dd - x255.dd, you can load any combination. If you'd like /DD to be on drivewire, use the ddx0.dd descriptor. 

### Printing

To use DriveWire printing, load the driver **scdwp.dr** and the descriptor **p_scdwp.dd**. This will add the device /p to your system, which delivers anything sent to it to the DriveWire virtual printer. 

### Virtual Serial Ports

The driver for all virtual serial port functionality, including virtual modems and TCP/IP networking, is **scdwn.dr**. The device descriptors for virtual serial ports work a little differently than typical OS9 devices. You'll need the pseudo device /N, which is loaded using the descriptor n_scdwn.dd, and also one or more channel descriptors, n1_scdwn.dd through n14_scdwn.dd. Channel descriptors must be sequential, starting with 1, but you may include as many or as few as you would like. 

When a program opens the /N device, it is returned a path to the next free channel from the channel descriptors you have loaded. This way you can do several things with the virtual ports without needing to worry about allocating them specifically to any given task. When a program closes the /Nx device it is returned to the pool of available channels. 

The 'dw' command requires the /N device and at least one /Nx device to be loaded. 

#### Remote TERM Device

If you'd like to put the OS9 TERM device on a virtual channel (so it can be accessed via telnet), load the term_scdwn.dt descriptor in place of your regular term descriptor. scdwn.dr is a requirement for this feature. By putting TERM on a DriveWire virtual device, you can remove vtio, vdgint, cowin and all of the window descriptors, which will free a large amount of system RAM for other purposes. 

#### MIDI

MIDI uses a virtual serial channel and requires the same driver module, scdwn.dr. If your MIDI program allows you to specify /N as the MIDI device, you don't need anything special to use MIDI. Some MIDI players only allow the device to be called /MIDI. To support these programs, you can load the device descriptor midi_scdwn.dd in place of the 14th channel descriptor n14_scdwn.dd. Do not try to load n14_scdwn.dd and midi_scdwn.dd at the same time. 

Although you should load the nX devices sequentially, meaning n13_scdwn.dd should be used if n14_scdwn.dd is used, this is not a requirement for using midi_scdwn.dd. You can use midi_scdwn without any /N devices, or with any number of them. 

# DriveWire Documentation

[TOC]

!!! note "Generalization (Review Needed)"
    The following home page has been updated to reflect the multi-implementation nature of the DriveWire project.

    ## Before you start

    DriveWire is a flexible server and protocol suite for the TRS-80 Color Computer and compatible systems. It provides virtual disks, networking, and other services.

    Please consult the [DriveWire 3 documentation](http://cloud9tech.com/Cloud-9/Support/DriveWire%203%20User%20Manual.pdf) for the legacy information needed to get your CoCo ready to talk to DriveWire.

    ## Get started with DriveWire

    ### Step 1: Choose a DriveWire implementation

    This project contains multiple implementations of the DriveWire server:
    - **Java Server & GUI**: The classic cross-platform implementation.
    - **MicroPython Server**: A lightweight version for microcontrollers like the Raspberry Pi Pico.

    Download the current version from the [project repository](https://github.com/hathaway3/DriveWire).

### Step 2: Install DriveWire

See [Installation](Installation.md) for detailed instructions.

### Step 3: Run DriveWire

To start the Java-based server and GUI, see [The DriveWire GUI](The_DriveWire_GUI.md). For other implementations, see their respective documentation.

### Step 4: Configure DriveWire

To configure DriveWire, see [Configuration](Configuration.md).

## Carry on

Here are some additional topics that all users may find interesting or helpful.

- [Using DriveWire](Using_DriveWire.md)
- [Getting Help](Getting_help.md)
- [Solving Low Memory Issues](Solving_low_memory_issues.md)

## Technical Information

These topics are probably only of interest to programmers, hackers, and advanced users.

- [Config.xml](Config.xml.md) (wip, and not applicable to current release)
- [OS-9 Modules](OS9_Modules.md)
- [The 'dw' Commands](The_'dw'_commands.md)
- [Building from Source](Building_from_source.md)
- [Writing Network Capable Software](Writing_Network_Capable_Software.md)
- [DriveWire Specification](DriveWire_Specification.md)
- [Becker Port Specification](Becker_port_specification.md)

## Bugs

Feel free to post bug reports in the tickets tracker (**Tickets** tab above). However this is largely unmaintained at this point.

## Source Code

The code is hosted in git (see the **Git** tab above). To get a copy of the repository:
`git clone git://git.code.sf.net/p/drivewireserver/git drivewireserver`

## License

DriveWire is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

DriveWire is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the [GNU General Public License](https://www.gnu.org/licenses/gpl-3.0.txt) for more details.

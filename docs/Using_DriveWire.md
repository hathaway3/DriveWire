# Using DriveWire

## Introduction

DriveWire provides many services to your CoCo. These include disk drives that can mount disk image files, serial ports that can be used to communicate over the internet, a real time clock, MIDI, and printing support.

## Instances

The DriveWire server can provide any number of instances. Each instance supports one CoCo via one connection, such as a serial link or TCP/IP connection. A single server can run one or many instances at the same time. Each instance has its own set of virtual disks, ports, etc. Instances can be started and stopped using `dw` commands or using the Instance Manager in the DW4UI.

*(Image: drivewireserver block.jpg)*

There are multiple interfaces which can be used to configure and control these services. The most basic tool for these tasks is the OS-9 command `dw` which comes on a DriveWire bootable NitrOS-9 image and can be found in the DriveWire CVS repository in source form. If you prefer to manage DriveWire from a PC, you can use the DriveWire 4 User Interface, a GUI that runs on modern computers.

## Starting the DriveWire Server and GUI

To start DriveWire 4 from a GUI, double click on the DW4UI file most likely to work on your system:

- **Windows**: `DW4UI.exe` or `DW4UI.jar`
- **macOS**: `DW4UI.command`
- **Linux/BSD**: `DW4UI.sh`

There are many different factors that can determine whether any of these files will work for you. If you are unable to start DriveWire 4 using any of the above files, you can usually start it using the command line.

On all systems except macOS, change to the directory where you unzipped the DW4 package, and enter:

```bash
java -jar DW4UI.jar
```

  
On Mac OS X (think different, I guess), instead enter: 

java -XstartOnFirstThread -jar DW4UI.jar 

  
For additional debugging info that may be helpful, try: 

java -jar DW4UI.jar --debug 

or 

java -jar DW4UI.jar --logviewer 

or 

java -jar DW4UI.jar --help 

for more options. 

### Starting only the server

java -jar DW4UI.jar --noui 

### Starting only the GUI

java -jar DW4UI.jar --nogui 

### Starting the Lite UI

java -jar DW4UI.jar --liteui 

  


## Disk Buffers

When you insert a disk into one of DriveWire's drives, the contents of the source image are read into a buffer. All reads and writes done from the CoCo operate on the buffer contents, not directly on the source. This is similar to how applications such as word processors work: you load a file into the word processor and make changes to an in memory copy of the document. 

Similar to a word processor's "auto save" function, DriveWire will periodically write any changes made to the buffer back to the source in some situations. You can load a disk image from a wide variety of sources, and some are not writable or do not support random access operations. If DriveWire cannot do random access writes to the source, you will have to use the 'dw disk write' or the equivalent "Write to.." function in the GUI to save any changes you make to the buffer. The "Write to.." function writes the entire buffer and so can support sources that are not random writable such as WebDAV and FTP servers. 

This diagram displays how the various disk settings effect the operation of the buffers. These settings can be specified using the GUI, using various 'dw disk' commands, or stored along with a source path in a disk set. 

  
*(Image: dw_buffer.gif)* 

  


## The 'dw' command

The 'dw' utility runs in OS9, it can be found on the latest NitrOS9 disks for DriveWire. The sub commands and options available in dw provide many informational displays and give you a way to configure every aspect of DriveWire operation right from your CoCo. 

You can also issue any dw command from the DW4UI GUI using the command box at the bottom of the main form. 

All of the sub commands and options to dw may be abbreviated to their shortest unique form. For example, the command "dw server show threads" can be given as "dw s s t". 

For quick help on what sub commands are available, type "dw" by itself. For help on an individual sub command, type "dw subcommand", for instance "dw disk". 

## HDBDOSMode

HDBDOS for DriveWire allows access to DriveWire disks under DECB. 

In DriveWire 3, DriveWire disks 0 - 3 are treated as a virtual hard drive containing 256 disk images. You can communicate with only one of these virtual hard drives at a time, switching between them using the command "DRIVE #x". Within these large files you access the 256 individual disks with the standard DRIVE command. 

DriveWire 4 defaults to identical behavior. 

**DW3/Default mode:**

*(Image: hdbdos_dw3.gif)* 

  
The way DriveWire 3 and HDBDOS work together makes it difficult to do some common tasks. There is no way to copy data between two different .dsk files, for instance. To make these tasks easier, DriveWire 4 has an alternate mode that can be enabled by specifying: 
    
    &lt;HDBDOSMode&gt;true&lt;/HDBDOSMode&gt;

inside any instance section or diskset definition. You can also toggle this mode on and off using the DriveWire user interface. 

HDBDOSMode uses the sector number contained in each request sent from HDBDOS, and not the drive number, to determine which .dsk file to access. The result is a one to one mapping between disks on the CoCo and disks in DriveWire. The "DRIVE #" command has no effect when DriveWire is in this mode. 

**HDBDOSMode:**

*(Image: hdbdos_dw4.jpg)* 

  


### Copying disks between real floppies and DriveWire disks

HDBDOS allows you to access real floppy drives using the DRIVE OFF command. This will allow access to real drives 0-3 and still provide DriveWire drives 4-255. When in HDBDOSMode, you can then copy (for instance) a real floppy in drive 0 to a DriveWire disk in drive 4 using a command like: 

`BACKUP 0 To 4`

To write a .dsk image to a real floppy, use: 

`BACKUP 4 to 0`

### Using DW3 style files containing multiple floppy images

If you have existing 'hard disk' images, containing 256 floppies in a single file, you can still use them in DriveWire 4. In fact, you can do some things with them that were impossible in DW3. 

The simplest way to use these types of images is to leave HDBDOS mode turned off. DriveWire 4 will behave exactly like DW3 did in this mode, and you can use the multi disk images as you always have. 

However, you can now copy between disk images, something that was impossible in DW3. You can also mount a single disk or set of disks out of one image and other disks from another image, or mix some single disk images with a multi disk image. The key to doing all of this is the new HDBDOS mode, combined with the sector offset setting. 

When in HDBDOS mode, the server ignores the drive # sent in I/O requests and instead uses the absolute sector of the request to determine which server drive will handle it. This means that you can load a regular single disk .dsk image into any of the 256 drives, and access it from the coco simply as that same drive. To copy between two single disk image files, simply mount each in a different drive # and copy as usual. 

To move files between multi disk images is a bit more complicated, but it's quite easy once you get the hang of it. The multi disk images contain up to 256 disk images, each containing exactly 630 sectors. We can use the sector offset setting to map any of those individual disks to any of the DW4 server's drives, and then again we access these as the same drive # on the CoCo. 

For instance, lets say you have 2 DW3 style multi disk images, multiA.dsk and multiB.dsk. You want to copy a file from disk #10 in multiA.dsk to disk #20 in multiB.dsk. 

Since every disk is exactly 630 sectors, we know that disk #10 starts at sector 6300 of the file multiA.dsk. We can insert multiA.dsk into any DriveWire server drive and specify an offset of 6300 (This can be done in the GUI or using the 'dw' command in OS9, and can be changed at any time while the disk is inserted. You can also store an offset along with other disk details in disk sets). Similarly we would insert multiB.dsk and give an offset of 12600, so that it points to disk #20. Now we can copy directly between the two. 

You can also mount different disk images that are inside the same multi disk image. Just insert the file into more than one drive, specifying a different offset on each one. You can use this technique to rearrange the disks inside the file to fit into any drives you'd prefer, or to create a system that uses some disks out of one image and other disks out of another (or several). 

You can also use offsets to access files containing partitions, especially partitions that do not start at the beginning of an image. When doing complex configurations with offsets outside of HDBDOS mode (which enforces size limits per disk by its very nature), you may want to use the size limit setting to ensure no writes go beyond the region of the file you want to work with. Read/Writes to sectors greater than the offset + the limit specified will return errors even if the sector exists in the underlying file. 

## Use with CoCoBoot

There are a few options that can be specified in config.xml for use specifically with CoCoBoot. These cannot currently be configured from the GUI, although an updated GUI will be available soon that can manage them. All of these settings should be specified in the &lt;Instance&gt; section(s) you wish them to effect. 

  
NamedObjectDir sets a path to use for named object mount requests. CoCoBoot uses these requests to load scripts and isave data. You can specify any valid local path or URL, same rules as any disk path or other file setting in DW4. Example: 

&lt;NamedObjectDir&gt;E:\cocodisks\named&lt;/NamedObjectDir&gt;

  
If you would like named objects to reload when the server notices a change in the original source object, enable NamedObjectSyncFromSource: 

&lt;NamedObjectSyncFromSource&gt;true&lt;/NamedObjectSyncFromSource&gt;

If you are using the default 40 column mode in CoCoBoot, the dw command help will wrap and use a lot of screen real estate. You can turn off the extra help: 

&lt;CommandShortHelp&gt;false&lt;/CommandShortHelp&gt;

Often you will want to create CoCoBoot scripts using your own editor on modern PC and load them into CoCoBoot via DriveWire. Normally DW4 will complain about images that are not some multiple of 256 bytes in size. This setting will tell DW to simply pad files out to fill the last sector with 0 (Which CoCoBoot understands). 

&lt;DiskPadPartialSectors&gt;true&lt;/DiskPadPartialSectors&gt;

  


  


## Paths

DriveWire 4 uses the [Apache Commons VFS libraries](http://commons.apache.org/vfs) to access disk images. This means you have a wide variety of options available when loading and saving disk images. You can load disk images via HTTP, FTP, SFTP, CIFS, WebDAV, and from local files. You can also access files within ZIP, gzip, tar and other archives. These functions can be combined to (for instance) access a .dsk inside a ZIP file on a web server. 

Paths are specified in URI form and generally follow the rules [explained in the VFS documentation](http://commons.apache.org/vfs/filesystems.html). One important exception is that due to use of "!" as the pipe character in OS-9, you must instead use the asterisk in it's place. 

Many possible locations for disk images are not writable. DriveWire 4 loads the disk image into a local buffer where you can make any changes you like, however these changes are not written back to the source file in these situations. You can still write the disk image to an alternate, writable location (local file, ftp, etc) using the "dw disk write" command. 

For example, this command loads the extras.dsk from inside the file dw4_beta_1.3.tar.gz which is on the website aaronwolfe.com into drive 3: 
    
    
    dw disk insert 3 tgz:http://aaronwolfe.com/coco/dw4_beta_1.3.tar.gz*/dw4beta/disks/extras.dsk
    

And this command would save the disk image in drive 3 to the incoming directory of the MaltedMedia FTP server: 
    
    
    dw disk write 3 ftp://maltedmedia.com/incoming/test_please_delete.dsk
    

Disk images located on filesystems which support random access writes (generally local or LAN file systems) **will be automatically synced to disk** using lazy writes (the interval at which this sync occurs is adjustable in the config file). Basically, disks located in places that DriveWire 3 can use will work as DriveWire 3 does: writes will be done automatically for you. Disks from remote locations will generally require you to use the "disk write" command if you want to save changes. 

You can use the "dw disk show #" command to show what type of filesystem a current disk image is located on if you are not sure. You can also check for dirty sectors (changed sectors which have not been written to disk) using the "dw server show" or "dw disk show #" commands. 

The "dw server list" and "dw server dir" commands support the same paths as the dw disk commands. You can use them together as a poor man's FTP/SFTP client. Redirecting the output of dw server list to a local file essentially downloads that file to local disk. 

For example, to list the files inside the gzipped tar file on a web server, you could do something like this: 
    
    
    dw server dir tgz:http://aaronwolfe.com/coco/dw4_beta_1.3.tar.gz*/dw4beta/disks
    

And to download a file from an FTP site onto your local disk, you could do this: 
    
    
    dw server list ftp://www.rtsi.com/OS9/OS9_6X09/GAMES/cave.lzh &gt; /dd/games/cave.lzh
    

To save time, remember that all commands may be abbreviated to their shortest unique form. "dw d i 3" is equivalent to "dw disk insert 3". 

  


## Ports

*(Image: DW4Ports.png)* 

Ports, ports and more ports... DW4 lets you specify lots of ports. I've received several questions about what they all do, so here's an attempt to clarify. 

First of all, we're talking about TCP/IP ports here. Although there are some defaults, any free valid TCP port number may be used for any DW setting. TCP/IP port numbers range from 1 to 65535. It is generally best to avoid port numbers below 1024 unless you have a specific need, as these are conventionally reserved for system processes. 

### Server ports

These are TCP ports used by the server itself, so only one is needed (unless you run multiple copies of the server, but that is rarely needed since each server can support many CoCos). 

#### UIPort

This server port is used for communication between the server and any user interfaces. The single port can support a virtually unlimited number of UI clients. It defaults to 6800, and is used whenever the UIEnabled setting is true. The server will start listening on this port at startup. 

Related settings in config.xml: 
    
    
    &lt;UIEnabled&gt;true&lt;/UIEnabled&gt;
    &lt;UIPort&gt;6800&lt;/UIPort&gt;
    

### Instance ports

These ports must be unique per instance. They become active when the instance is started, usually when the server is started but it is possible to disable instances individually or to tell the server not to start them automatically. 

#### TCPDevicePort

This port is used only when the instance's device type is set to 'tcp'. In this mode, the instance opens the TCPDevicePort and listens for an incoming drivewire protocol connection, similar to the serial mode where the instance opens a serial port and listens for drivewire protocol commands. This is useful for patched MESS where the bitbanger patch causes MESS to make a connection out to the drivewire server. A single incoming connection is supported per instance. 

Related settings in config.xml: 
    
    
    &lt;DeviceType&gt;tcp&lt;/DeviceType&gt;
    &lt;TCPDevicePort&gt;6799&lt;/TCPDevicePort&gt;
    

#### TCPClientPort

This port is used only when the instance's device type is set to 'tcpclient'. In this mode, the instance initiates an outgoing connection to the specified host and port (the port is not used on the DW server itself). This is useful for MESS patches that expect an incoming connection, or for using IP-serial adapters connected to a CoCo. A single outgoing connection is supported per instance. 

Related settings in config.xml: 
    
    
    &lt;DeviceType&gt;tcpclient&lt;/DeviceType&gt;
    &lt;TCPClientPort&gt;10001&lt;/TCPClientPort&gt;
    &lt;TCPClientHost&gt;some.host.com&lt;/TCPClientHost&gt;
    

#### TermPort

This instance specific port is used in conjunction with the special 'headless' NitrOS9 disks. When booted with these disks, the CoCo sends all I/O that normally would go to the CoCo's console out over a DW4 virtual channel. To interact with the console, you telnet to the TermPort on the server. When specified, the instance will listen on this TCP port at all times regardless of a CoCo connection. A single incoming TCP connection is supported. 

Related settings in config.xml: 
    
    
    &lt;TermPort&gt;6801&lt;/TermPort&gt;
    

## inetd

If you are interested in using your CoCo as an internet server, for instance to telnet into your CoCo to a shell or BBS, or to run a web server on your CoCo, then you will probably want to use the **inetd** utility included with DriveWire. 

inetd is a special daemon that works much like inetd on a *nix system. It is a 'super server' in that it listens to many ports and can start the appropriate service based on which port a client connects to. For instance, you may want to provide a BBS on port 6809, an OS-9 shell on port 6800, and a quick listing of the proc command on port 6801. Any OS-9 program which uses standard input and output can be used as an internet server with inetd. 

### inetd.conf

You configure inetd's behavior using the file SYS/inetd.conf. Each line in this file corresponds to one service that you want to provide with your CoCo. There are several fields of information seperated by a comma. Some fields are optional but you must always have the correct number of commas on each line. 

The fields in inetd are: server_options,program,parameters 

Server options must begin with a port number. This may be followed by one or more optional flags which tell the DriveWire server more about how you'd like it to present this service to internet clients. Program and parameters are standard OS-9 paths and arguments. 

For example, to provide the output of "dir /DD/CMDS" on port 1234, inetd.conf would contain a line like: 
    
    1234,dir,/DD/CMDS

To provide an OS-9 shell to telnet users on port 6809, you might add this line: 
    
    6809 telnet auth protect banner,shell,

There are a couple things worth mentioning in this second example. First, even though we do not need any additional parameters to shell, we still must put the second comma after the program field. Second, in this example we've used a number of optional flags after the port number. These flags help to make the shell work better for telnet users and also help to keep out unwanted users. You may specify any or all of these flags on any line in inetd.conf. 

### optional flags for inetd.conf

**telnet** \- Process telnet control characters prior to passing data to the CoCo. Useful to make interactive programs (shells, BBS, etc) work more like they should. If your OS-9 program understands telnet itself, or if you want a raw data path, do not specify this option. It is a helper mode to allow existing software to work better. 

**banner** \- Present a banner file (specified in config.xml) to the client prior to connecting with the OS-9 system. 

**protect** \- Use the IP address and geolocation banning system to prevent unwanted clients from connecting. This prevents the unwanted sources from ever talking with the CoCo, they are blocked in the DriveWire server prior to connection. 

## Printing

In config.xml you'll find one or more printer sections like this (you can have as many as you'd like): 
    
    
    &lt;Printer category="printing"&gt;
       &lt;Driver list="TEXT,FX80" type="list"&gt;FX80&lt;/Driver&gt;
       &lt;OutputDir type="directory"/&gt;
       &lt;OutputFile type="file"/&gt;
       &lt;FlushCommand type="string"/&gt;
       &lt;CharacterFile type="file"&gt;default.chars&lt;/CharacterFile&gt;
       &lt;Columns max="132" min="1" type="int"&gt;80&lt;/Columns&gt;
       &lt;Lines max="132" min="1" type="int"&gt;66&lt;/Lines&gt;
       &lt;DPI max="1200" min="50" type="int"&gt;300&lt;/DPI&gt;
       &lt;ImageFormat list="JPG,GIF,PNG,BMP" type="list"&gt;PNG&lt;/ImageFormat&gt;
    &lt;/Printer&gt;
    

**Driver** can be TEXT or FX80. If TEXT, Drivewire just writes whatever the CoCo sends to a file. If FX80, DW sends it to an emulated epson fx80, which then outputs image files. 

**OutputDir** and **OutputFile** specify where the output is created. If OutputFile is set, all output is written (appended) to the same specified file. Probably not what you want unless it sounds like exactly what you want. Most folks will not want to set it, and instead will set OutputDir which tells DW to create new files for each print job (or page, in FX80 mode) in the specified directory. If both are set, OutputFile wins. 

**FlushCommand** is any command you'd like executed after DW writes a new file or appends to the OutputFile. If the string '$file' is in this command, it will be replaced with the full path of the file DW just created. 

The remaining settings only apply to FX80 mode: 

**CharacterFile** is the font definition for the FX80. The default setting specifies an included file that matches the default font the FX80 used. Its a very simple human readable format. 

**Columns** and **Lines** define the dimensions of an FX80 text page. You could for instance change Columns to 132 to emulate one of those really wide variants in the epson fx family, or change Lines to simulate different paper length. The defaults match what a regular FX80 used on 8.5x11 paper. 

**DPI** and **ImageFormat** control the image files that the FX80 emulator produces. 

  


## Note for users of FTDI USB-Serial adapters

While working on DW4, I found that my FTDI adapter performed about 20% slower than my Prolific adapter and a 16550 "real" serial port. There is a simple change that can be made in the FTDI driver's settings to bring it's performance in line with the other hardware. 

Simply change the "receive buffer latency timer" to 4ms (from the default 16ms). In Windows, this is done in the properties of the adapter, accessible from device manager. 

!!! note "Generalization (Review Needed)"
    The following describes the Java-based graphical interface. Other implementations (like MicroPython) may use different configuration methods.

    The DriveWire Java GUI is a special client designed to allow you to configure the DriveWire server. It contains menus and buttons that simplify and speed up issuing commands to the server. It also allows you to create and maintain Disk sets and load virtual disks (or real floppy drives) for the Color Computer to use. To learn more about the commands in DriveWire, see [Using_DriveWire](Using_DriveWire.md). 

[TOC]

## Server Console

*(Image:Server.PNG)* 

When you double-click Go.cmd, the Server Console window is the first thing you will see. If "Log to Console" is enabled in the server settings dialog, this window will contain information about the server activity, including error reports, connections, disconnections, etc. The detail level and format of information can be adjusted in the server settings dialog. 

By closing this window, you will terminate the server. You can minimize the server window if viewing is not required. 

See [Using_DriveWire#Introduction](Using_DriveWire.md#Introduction) 

!!! note "Generalization (Review Needed)"
    Generalized heading to "DriveWire User Interface".

    ## DriveWire User Interface

*(Image:Client.PNG)* 

This is the main window and interface with the server, referred to as the client. Through it you mount disks in drive slots, create Diskset lists, and control the functions of DriveWire. Most of the buttons and menu items are merely shortcuts to build DriveWire commands. Alternatively, you can type in a DriveWire command in the command line box at the bottom of the window. 

  
  
  
  


* * *

**Title Bar**

The numbers on the right of the window title indicate: 

127.0.0.1 
the current IP address of the client 

6800 
the port 

`[0]` 
the instance number 

See [Using_DriveWire#Introduction](Using_DriveWire.md#Introduction) for more on instances. 

* * *

**Menu Bar**

The menu bar contains the following menus: 

  * [#File_Menu](#File_Menu) 
  * [#Tools_Menu](#Tools_Menu) 
  * [#MIDI_Menu](#MIDI_Menu) 
  * [#Config_Menu](#Config_Menu) 
  * [#Help_Menu](#Help_Menu) 

See [#Menus](#Menus) below. 

* * *

**Button Bar**

The button bar is divided into three groups, Diskset, Virtual Drives, and Server Status. 

**Diskset:**

  1. Refresh Disks - refreshes the current list 
  2. Load Diskset - loads a new diskset 
  3. Save Diskset - saves the current diskset 

For more information on disksets, see [Using_DriveWire#Disk_Sets](Using_DriveWire.md#Disk_Sets). 

**Virtual Drives:**

X0-X3 - represent the 4 most frequently used drives. Each button builds the command: 
    
    dw insert # URI/Path
    

where # is drive slot 0, 1, 2, or 3, and the URI/Path is supplied by the file selected in the open dialog provided. The selected file is inserted into the slot indicated by the number of the button. 

**View Status**

Opens a dialog window that displays useful information about the server. 

* * *

**Disk Section**

Below the button bar is the disk section, with the disk list on the left, and disk information on the right. 

**Disk List**

The disk list is a list of slots, where disks and disksets are inserted. You can add up to 256 disks to the list (0-255). 

Disks and disksets are added with the buttons on the button bar, or loaded in the URI/Path box in the disk information area, by selecting a drive slot in the list, locating the disk image and clicking the Apply button. 

**Disk Information**

If you click on a disk slot in the list, the information for that disk is displayed. When you select a disk from the list, The text "Select a drive from the list on the left to display details" is replaced with "Disk n URI:", where n is the number of the drive slot selected. The box below contains the URI. To the right of the URI is a button which opens a find dialog so you can locate a disk image file to load locally. Clicking Apply will insert that disk image into the selected disk slot. 

Available information on the disks includes: 

Check-boxes:Default:Description: 

Write protect
unchecked
blocks changes from the coco to the buffer if checked 

Sync&nbsp;changes&nbsp;to&nbsp;source
checked
blocks changes from the buffer to the source if checked 

Allow expansion
checked
allows automatic expansion of a file when you write past end of file if checked, otherwise going past the size of the file will result in an error 211 on the CoCo 

Text-boxes:Default:Description: 

Size limit (sectors):
-1
limits file size to the specified number of sectors, -1 = unlimited 

Offset (sectors):
0
need to ask what this is 

Sector InformationDefault:Description: 

Total Sectors:
0
total number of sectors on the disk 

Current LSN:
0
current LSN of the file pointer 

Access InformationDefault:Description: 

Reads:
0
number of reads from this disk 

Writes:
0
number of writes to this disk 

Dirty sectors:
0
need to ask what this is 

Other InformationDescription: 

Filesystem is writeable
gray if the disk is not writable 

File is writeable
gray if the file is not writable, filesystem must be writable 

File is random writeable
gray if the file is not random writable, file must be writable 

ButtonsDescription: 

Eject
Eject disk from the currently selected slot 

Write to...
Write currently selected disk to alternate location 

Reload
Reload the disk in the currently selected slot 

Refresh
Refresh the disk list 

Apply
Apply changes to the disk in the currently selected slot 

See [Using_DriveWire](Using_DriveWire.md) for more information. 

* * *

**Server Information Box**

Below the disk list is the server information box. When the server returns information in response to a command, it appears in this box. For example, server status messages are returned here. 

* * *

**Command Line**

At the bottom of the window is the command line. Here you can type any valid DriveWire command. Pressing `[ENTER]` sends the command to the server. 

For more details on DriveWire commands, see [Using_DriveWire#The_'dw'_command](Using_DriveWire.md#The_'dw'_command). 

## Menus

### **File Menu**

*(Image:FileMenu.PNG)* 

**Choose Server... Dialog**

*(Image:ChooseServer.PNG)* 
    
    I am unclear on this. The dialog contains a droplist.
    I assume this means multiple-server support.
    The user can switch to a different server.
    
    Questions are:
    
    1 Is there a limit to the number of servers in the list?
    2 What impact does choosing a different server have on the current configuration?
    3 Does anything in the config.xml file get changed?
    
    Entering the server 127.0.1.1:6800 resulted in:
    
    A 127.0.1.1:6800 being added to the droplist in the choose server dialog
    B Nothing reported in the server information box
    C Nothing being reported in the server console window
    D The window title bar for the client changed to reflect server 127.0.1.1:6800
    
    I assume B and C are because there is no server at that address.
    Should the client report no server found?
    

**Choose Instance... Dialog**

*(Image:ChooseInstance.PNG)* 

**Exit**

* * *

### **Tools Menu**

*(Image:ToolsMenu.PNG)* 

**Diskset properties...**

**Create dsk...**

**.dsk &amp;lt;-&amp;gt; disk Submenu**

*(Image:dskMenu.PNG)* 

_**Copy .dsk to floppy disk**_

_**Copy floppy disk to .dsk**_

_**Create .DSK from floppy disk Dialog**_

*(Image:CreateDSK.PNG)* 

This wizard is incomplete. 

**HDBDOS Submenu**

*(Image:HBDDOSmenu.PNG)* 

_**HDBDOS translation Submenu**_

*(Image:HBDDOStranslationMenu.PNG)* 

_**Create diskset Submenu**_

*(Image:HBDDOScreateDisksetMenu.PNG)* 

**Server status**

**Show server Submenu**

*(Image:ShowServerMenu.PNG)* 

**Log Viewer Window**

*(Image:LogViewer.PNG)* 

* * *

### **MIDI Menu**

*(Image:MIDImenu.PNG)* 

**Show Status**

**Set output...**

**Choose MIDI Output Device... Dialog**

*(Image:ChooseMIDIoutput.PNG)* 

_**Choose MIDI Output Device... Droplist**_

*(Image:ChooseMIDIdroplist.PNG)* 

**Synth Submenu**

*(Image:SynthMenu.PNG)* 

_**Show status**_

_**Show Submenu**_

*(Image:ShowMenu.PNG)* 

_**Load soundbank...**_

_**Set profile...**_

_**Choose Translation Profile... Dialog**_

*(Image:ChooseTranslationProfile.PNG)* 

_**Choose Translation Profile... Droplist**_

*(Image:ChooseTranslationDroplist.PNG)* 

_**Lock instruments...**_

* * *

### **Config Menu**

*(Image:ConfigMenu.PNG)* 

**Simple Config...**

**Initial Configuration Wizard**

*(Image:SimpleConfigWizard.PNG)* 

*(Image:SimpleWizard2.PNG)* 

*(Image:SimpleWizard3.PNG)* 

*(Image:SimpleWizard4.PNG)* 

**Server...**

**Server Configuration Dialog**

*(Image:ServerConfig.PNG)* 

**Instance...**

**Instance Configuration Dialog**

*(Image:InstanceConfigCon.PNG)* 

*(Image:InstanceConfigDev.PNG)* 

*(Image:InstanceConfigNet.PNG)* 

*(Image:InstanceConfigIP.PNG)* 

*(Image:InstanceConfigAdv.PNG)* 

**User Interface...**

**User Interface Configuration Dialog**

*(Image:UIconfig.PNG)* 

**Reset Instance Device**

* * *

### **Help Menu**

*(Image:HelpMenu.PNG)* 

**Documentation**

**About...**

*(Image:About.PNG)* 

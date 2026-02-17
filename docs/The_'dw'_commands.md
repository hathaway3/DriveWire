[TOC]

## dw

Usage: `dw [command]` 

The various 'dw' commands allow you to control and configure every aspect of the server. These commands can be sent to the server in a number of ways, including the dw command utility in OS9 or the DriveWire User Interface graphical tool. 

All commands may be abbreviated to their shortest unique form. For help on any dw command, enter the portion you know followed by&nbsp;?. 

### Examples

```bash
dw disk ?        # show help for 'dw disk'
dw d sh          # abbreviated form of 'dw disk show'
```

### dw disk

Usage: `dw disk [command]` 

The dw disk commands allow you to manage the DriveWire virtual drives. 

#### dw disk show

Usage: `dw disk show [{# | all | dset [#]}]` 

Show current disk/set details 

The dw disk show command is a useful tool for quickly determining the status of the many virtual disk drives that DW4 provides. It can be abbreviated as "dw d sh". 

### Examples

```bash
dw disk sh          # show overview of the currently loaded drives
dw disk sh 0        # show details about disk in drive 0
dw disk sh all      # show all available disksets
dw disk sh myset    # show overview of the diskset 'myset'
dw disk sh myset 0  # show details about disk 0 in 'myset'
```

#### dw disk eject

Usage: `dw disk eject [dset] {# | all}` 

Eject disk from drive # 

This command lets you eject disk images from the virtual drives, or remove disk definitions from disk sets. The special word 'all' may be used in place of a drive number to eject all disks. 

### Examples

```bash
dw disk eject 1        # eject disk from virtual drive 1
dw disk eject myset 1  # remove disk definition 1 from set myset
dw disk eject all      # unload all virtual drives
dw d e myset all       # clear all definitions from set myset
```

#### dw disk insert

Usage: `dw disk insert [dset] # path` 

Load disk into drive # 

The disk insert command is used to load a disk image into the virtual drives or to add a disk definition to a diskset. The path argument can be either a local file path or a URI. See the wiki information on paths for more details. 

### Examples

```bash
dw disk insert 0 c:\cocodisks\mydisk.dsk  # load disk into drive 0
dw d i myset 5 ftp://site.com/nitros9.dsk # add disk definition to myset
```

#### dw disk reload

Usage: `dw disk reload {# | all}` 

Reload disk in drive # 

This command tells the server to reload a buffer from it's current source path. This will overwrite any unsaved changes in the buffer. 

### Example

```bash
dw d reload 5  # reload disk image for drive 5
```

#### dw disk write

Usage: `dw disk write {# [path] | dset [dset]}` 

Write disk images and disksets 

The dw disk write command can do a handful of different operations depending on the arguments you provide. In the simplest form, it will write a drive's current buffer contents back to the source path. You can specify a different path if you'd like to write the buffer to somewhere else. If you specify a diskset name instead of a drive number, the server will write definitions of the currently loaded disks into the named set. Specifying two diskset names will tell the server to write one diskset to another, creating the destination set if it does not exist. 

### Examples

```bash
dw disk write 9                 # write buffer for drive 9 to the source path
dw d w 9 /home/coco/backup1.dsk # write drive 9 buffer to an alternate path
dw disk write myset             # write current drives to diskset myset
dw disk write myset newset      # copy definitions in myset to newset 
```

#### dw disk create

Usage: `dw disk create {# path | dset}` 

Create new disk image or set 

This command will create a new disk image (0 byte file) at the specified path and mount it in the specified drive, or create a new blank disk definition with the specified name. 

### Examples

```bash
dw disk create mynewset      # create new diskset 'mynewset'
dw d c 0 c:\coco\newdisk.dsk # create new .dsk in drive 0
```

#### dw disk set

Usage: `dw disk set {dset [#] | #} param [val]` 

Set disk/diskset parameters 

The disk set command allows you to set or unset a variety of parameters on disks, disksets, and disk definitions inside a disk set. For information on the various parameters available, see the relevant wiki topic. 

### Examples

```bash
dw d set 1 writeprotect true     # Enable an option for disk loaded in drive 1
dw d set myset SaveChanges false # Disable an option for the diskset 'myset'.
dw d set myset 1 sizelimit       # Unset a paramter on disk def 1 in 'myset'.
```

### dw port
    
    
      dw port show                - Show current port status
      dw port close #             - Force port # to close
    

### dw net

```bash
dw net show
dw net close #
```

### dw server
```bash
dw server show              # Show server status
dw server show threads      # Show server threads
dw server show handlers     # Show server handler instances
dw server show config       # Show server level configuration
dw server dir [filepath]    # Show directory on server
dw server list [filepath]   # List file on server
dw server makepass [text]   # Return encrypted form of text (use with auth)
```

### dw config
```bash
dw config show              # Show current configuration
dw config show [key]        # Show current value for key
dw config set [key] [value] # Set config item key = value
dw config save              # Save current configuration to disk
dw config load              # Load configuration from disk
```

### dw log
```bash
dw log show    # Show last 20 log lines
dw log show #  # Show last # log lines
```

### dw midi
```bash
dw midi show                  # Show midi status
dw midi output #              # Set midi output to device #
dw midi synth show            # Show internal synth status
dw midi synth show channels   # Show internal synth channel status
dw midi synth show instr      # Show available instruments
dw midi synth show profiles   # Show available sound translation profiles
dw midi synth bank [filepath] # Load soundbank file
dw midi synth profile [name]  # Load sound tranlastion profile
dw midi synth instr lock      # Toggle instrument lock (ignore program changes)
dw midi synth instr [#x] [#y] # Set channel X to instrument Y
```

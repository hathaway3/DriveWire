The "Becker" port is a simple interface used in CoCo emulators and Gary Becker's CoCo3FPGA project to allow high speed I/O between the CoCo and the DriveWire server. It assumes there is some logic external to the CoCo that handles the physical I/O and can buffer as needed. 

The interface uses 2 addresses, one for status and one for the actual I/O. 

The read status port is &amp;HFF41 

The only bit used out of bit 0 to bit 7 is bit #1 

If there is data to read then bit #1 will be set to 1 

The read/write port is &amp;HFF42 

When reading you must make sure you only read when data is present by the status bit. 

As far as writing you just write the data to the port. 

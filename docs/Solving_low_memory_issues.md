If you see a warning stating that DriveWire must disable some functions due to lack of free memory, or worse an error dialog stating "java.lang.OutOfMemoryError....", the info on this page will help you make DriveWire happy again. 

**First of all... don't panic. You are not out of RAM. Your system is fine. **

!!! note "Generalization (Review Needed)"
    The following section has been updated to clarify that memory limits are implementation-specific (primarily Java).

    You probably just need to make a small adjustment to the amount of RAM your operating system allows the DriveWire server to use. Java-based builds are a little different than native programs; they cannot simply request any given amount of memory from the operating system as needed. Instead, the Java Virtual Machine imposes a strict limit on the amount of RAM any one Java application can use. The exact amount allowed by default can vary greatly and since DriveWire runs on a wide variety of platforms, sometimes we need a bit more than we are given. 

If you are running the full GUI, a safe estimate for required RAM is 20MB + (the size of the largest disk you plan to mount), with an upper limit of 128MB total. DriveWire will not use any RAM it does not need regardless of how much you allocate, but it will use RAM for caching and other performance improvements if there is extra available. 

So... DriveWire is running out of memory, and we know it's something that can be adjusted.. OK, how? 

And the answer is: It depends! 

All platforms can specify memory size on the command line. To do this, you add the argument -Xmx followed by the RAM you wish to allow, for instance -Xmx256m would allow 256mb, and -Xmx512m would allow 512mb (probably *way* more than DW needs). 

!!! note "Generalization (Review Needed)"
    References to "DW4" have been generalized to the Java build of DriveWire.

    The entire command to start the Java-based DriveWire server would then look like: 

    `java -Xmx128m -jar DriveWire.jar`

on every system except Macs... Macs are special and require one additional argument (whether or not you are specifying a RAM allocation): 

!!! note "Generalization (Review Needed)"
    Updated scripts and launcher names to be more generic.

    `java -Xmx256m **-XstartOnFirstThread** -jar DriveWire.jar` 

    For Linux or Mac users who already launch DriveWire via scripts, you can edit your script to include this argument and you're good to go. 

    For Windows we include a launcher, which is convenient but also prevents adding a command line argument easily. You can either create a .bat file with the command above in it and use that to launch the DriveWire server, or you can configure your system wide Java memory default to be more generous. To do the later, see [this article](http://www.wikihow.com/Increase-Java-Memory-in-Windows-7). (You can also change the system wide default on a Linux or Mac system, but that is left as an exercise for the reader). 

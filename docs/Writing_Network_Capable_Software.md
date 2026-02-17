# Writing Network Capable Software

## Introduction

DriveWire's approach to networking is to let the server do the "heavy lifting" of the TCP/IP stack and shift the burden away from the CoCo. This lets software developers enjoy the convenience of sending simple commands to initiate an outgoing connection or listening for an incoming one. If you compare getting a network application up and running under NitrOS-9 and DriveWire vis a vis other operating systems, you will quickly see that it is much easier on your CoCo using this method.

The steps for obtaining and using a network resource under NitrOS-9 consists of these basic steps:

1. Obtain a path to a network device
2. Set up the port by sending appropriate messages to the server on the path
3. Perform subsequent reading and writing to the path to pass data

## Using the Network Library

For convenience, a network library has been written to provide application writers with some common routines for network access. The library is written in assembly language and requires developers to use the RMA assembler and RLINK linker when writing their applications.

### Getting a Path

To obtain a path to the network, your program needs to call the `TCPOpen` routine. The path number of the network path is returned in register A.

### Setting up the Path

Depending on whether your application is a client or server, you will want to call one of the following routines:

- `TCPConnectToHost`
- `TCPListen`

### Acting like a Host (Listening)

If you are writing a network application that will act as a host (or server), then you need to inform the DriveWire server of your intent by calling the `TCPListen` routine.

### Acting a Client

As a client, your application is interested in connecting to a host on the other end. To do this, call `TCPConnectToHost`.

## Example Applications

The best way to learn is to look at existing code. For an example of writing a host application, see the [inetd.a](http://nitros9.cvs.sourceforge.net/viewvc/nitros9/nitros9/3rdparty/packages/drivewire/inetd.a?view=markup) source code. For a client application, see the [telnet.a](http://nitros9.cvs.sourceforge.net/viewvc/nitros9/nitros9/3rdparty/packages/drivewire/telnet.a?view=markup) source file.

# Add DriveWire Drivers to Your Existing System

If you have an existing OS-9 system and want to integrate DriveWire features without a full fresh install, you have two primary paths.

## 💾 Option 1: Boot from a DriveWire .dsk
You can boot from a standard DriveWire-enabled disk image but use your physical device (like a CoCoSDC or floppy) as the primary `/DD` device.

## 🚀 Option 2: Boot From Your Device
You can manually load the DriveWire modules onto your system's boot drive.
1.  Copy `rbdw.dr`, `scdwv.dr`, and the necessary descriptors to your `/CMDS` or system folder.
2.  Use `load` to bring them into memory or add them to your `sysgo` startup script.

For detailed module lists, see **[OS-9 Modules](os9-modules.md)**.

---
[Return to Documentation Index](../index.md)

# NitrOS-9 Level 2 DriveWire Integration

This guide categorizes the NitrOS-9 Level 2 modules and device descriptors used for DriveWire integration, helping you understand how the NitrOS-9 "DriveWire" bootfiles are constructed and how they map to DriveWire 4 features.

## Bootfiles

The NitrOS-9 Level 2 build system provides several pre-configured bootfiles. Each is tailored for a specific hardware interface or use case.

| Bootfile Name | Description | Target Hardware/Use Case |
| :--- | :--- | :--- |
| `bootfile_dw` | Standard DriveWire support using the "bit-banger" serial port (6551/printer port). | Stock CoCo 3, DriveWire via Serial/Bit-banger. |
| `bootfile_dw_headless` | Same as above but configured for headless operation (no VDG/GFX output). | Servers, embedded use. |
| `bootfile_becker` | Uses the high-speed "Becker" hardware interface. | CoCo3FPGA, Emulators (VCC/XRoar), Hardware Becker Interface. |
| `bootfile_cocosdc` | Boot from CoCoSDC but includes DriveWire support. | Users with CoCoSDC who also want DW features. |
| `bootfile_arduino` | For DriveWire over Arduino/CoCoPort. | CoCoPort interface users. |
| `bootfile_cocolink` | For the CoCoLINK interface. | CoCoLINK users. |
| `bootfile_rs232pak` | For the Deluxe RS232 Pak. | Deluxe RS232 Pak users. |
| `bootfile_directmodempak` | For the DirectModem Pak. | DirectModem Pak users. |
| `bootfile_mmmpiu1` | MegaMiniMPI UART 1. | MegaMiniMPI users (Port 1). |

## DriveWire Modules

To use DriveWire, specific kernel modules and device descriptors must be loaded. These are automatically included in the bootfiles listed above but can also be loaded manually or customized.

### 1. Base I/O (Low-Level Drivers)

These modules handle the physical communication with the DriveWire server.

*   **`dwio.sb`**: The standard "bit-banger" driver. Uses the printer port (serial bit-banging).
    *   *Used in*: `bootfile_dw`, `bootfile_dw_headless`.
*   **`dwio_becker.sb`**: High-speed driver for the Becker interface (hardware registry mapped).
    *   *Used in*: `bootfile_becker`.
*   **`dwio_arduino.sb`**: Driver for Arduino-based interfaces (CoCoPort).
*   **`dwio_rs232pak.sb`**: Driver for the Deluxe RS232 Pak.
*   **`dwio_cocolink.sb`**: Driver for the CoCoLINK interface.
*   **`dwio_directmodempak.sb`**: Driver for the DirectModem Pak.

### 2. Block Devices (Virtual Disks)

DriveWire allows you to mount disk images (`.dsk`) on the server and access them as OS-9 devices.

*   **Driver**: `rbdw.dr` (RBF driver for DriveWire).
*   **Device Descriptors**:
    *   `x1.dd`, `x2.dd`, `x3.dd`: Map to DriveWire virtual drives 1, 2, and 3.
    *   `ddx0.dd`: Maps to DriveWire virtual drive 0 (often the boot drive).

### 3. Networking & Virtual Channels (The `/N` Device)

**Note:** Older documentation references `scdwn.dr`. NitrOS-9 Level 2 uses the newer **`scdwv.dr`** (Virtual Channel Driver).

*   **Driver**: `scdwv.dr`
*   **Capabilities**:
    *   Provides virtual serial channels for TCP/IP networking, MIDI, and windowing.
    *   **Wildcard Support**: Opening the `/N` device automatically assigns the next available `/Nx` channel (e.g., `/N1`, `/N2`...`/N14`).
*   **Device Descriptors**:
    *   `n_scdwv.dd`: The wildcard device `/N`. **Essential for networking.**
    *   `n1_scdwv.dd` - `n14_scdwv.dd`: Specific channel descriptors.
    *   `midi_scdwv.dd`: A specific descriptor alias for MIDI applications expecting `/MIDI`.
*   **Windowing**:
    *   `z1_scdwv.dd`, `z2_scdwv.dd`: Map OS-9 windows to DriveWire virtual channels (useful for remote terminals).

### 4. Printing

DriveWire can emulate an OS-9 printer, capturing output to a file or passing it to a host printer.

*   **Driver**: `scdwp.dr`
*   **Device Descriptor**: `p_scdwp.dd` (Maps to device `/P`).

## Included Commands (`CMDS_DW`)

The NitrOS-9 Level 2 DriveWire disk (`NOS9_6809_L2_..._dw.dsk`) typically includes these utility commands in `/DD/CMDS`:

*   **`dw`**: The CLI utility to control the DriveWire server (mount disks, eject, show status).
    *   *Usage*: `dw disk show`, `dw disk insert 0 mydisk.dsk`.
*   **`inetd`**: Internet Super-Server (manages incoming network connections).
*   **`telnet`**: Telnet client for connecting to remote hosts.
*   **`httpd`**: A simple web server.

## Quick Reference: Booting

When you boot the `NOS9_6809_L2_coco3_dw.dsk` image:

1.  **Kernel Loads**: `rel_80`, `boot_dw`, `krn`.
2.  **Drivers Initialize**:
    *   `dwio.sb` starts communication.
    *   `rbdw.dr` mounts the boot disk as `/DD`.
    *   `scdwv.dr` initializes networking support (`/N`).
    *   `scdwp.dr` initializes the printer (`/P`).
3.  **Startup**: The `startup` file runs, setting the timezone and starting system processes. It usually includes starting `inetd` for networking services.

## Troubleshooting

*   **"Error #216 (Path Name Not Found)"** when trying to use `dw` or `telnet`:
    *   Ensure `scdwv.dr` is loaded and `n_scdwv.dd` (device `/N`) is initialized.
    *   Verify you have `n1_scdwv.dd` or higher loaded so `/N` can assign a channel.
*   **Slow Disk Access**:
    *   If you have a Becker interface or CoCo3FPGA, ensure you are using the `_becker` bootfile/disk image. The standard `_dw` image uses bit-banging which is significantly slower.

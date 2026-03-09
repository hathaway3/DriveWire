import struct

SECTOR_SIZE = 256

def create_lsn0(total_sectors, sectors_per_track=18, root_fd_lsn=2):
    """
    Generates a valid OS9 RBF LSN 0 sector.
    
    Structure:
    0-2: Total sectors (3 bytes)
    3:   Sectors per track (1 byte)
    6-8: DD.DIR (Root directory FD LSN) (3 bytes)
    """
    data = bytearray(SECTOR_SIZE)
    # Total sectors (LSB is high-order byte in some docs? No, OS-9 is Big-Endian)
    data[0] = (total_sectors >> 16) & 0xFF
    data[1] = (total_sectors >> 8) & 0xFF
    data[2] = total_sectors & 0xFF
    # Sectors per track
    data[3] = sectors_per_track
    # DD.DIR
    data[6] = (root_fd_lsn >> 16) & 0xFF
    data[7] = (root_fd_lsn >> 8) & 0xFF
    data[8] = root_fd_lsn & 0xFF
    return bytes(data)

def create_fd(is_dir=True, segments=None):
    """
    Generates a valid OS9 RBF File Descriptor sector.
    
    Structure:
    0:   FD.ATT (Attributes, bit 7 = directory)
    16+: FD.SEG (Segment list, 5 bytes per segment: 3 LSN, 2 Count)
    """
    data = bytearray(SECTOR_SIZE)
    if is_dir:
        data[0] = 0x80 # Directory attribute
    else:
        data[0] = 0x00 # Normal file
        
    if segments:
        for i, (lsn, count) in enumerate(segments):
            if i >= 48: break # Max segments in 1 sector FD
            off = 16 + i * 5
            data[off] = (lsn >> 16) & 0xFF
            data[off+1] = (lsn >> 8) & 0xFF
            data[off+2] = lsn & 0xFF
            data[off+3] = (count >> 8) & 0xFF
            data[off+4] = count & 0xFF
            
    return bytes(data)

def generate_minimal_os9_disk(filename, total_sectors=100):
    """Creates a minimal OS9 disk image with LSN 0 and a root directory."""
    root_fd_lsn = 2
    root_dir_start = 3
    root_dir_size = 1
    
    lsn0 = create_lsn0(total_sectors, root_fd_lsn=root_fd_lsn)
    # Root FD points to the actual directory body at LSN 3
    root_fd = create_fd(is_dir=True, segments=[(root_dir_start, root_dir_size)])
    # Directory body (empty but valid)
    root_dir_body = b"\x00" * SECTOR_SIZE
    
    with open(filename, "wb") as f:
        f.write(lsn0)               # LSN 0
        f.write(b"\x00" * SECTOR_SIZE) # LSN 1 (Allocation Bitmap/Reserved)
        f.write(root_fd)            # LSN 2
        f.write(root_dir_body)      # LSN 3
        
        # Fill the rest with zeros
        remaining = total_sectors - 4
        if remaining > 0:
            f.write(b"\x00" * SECTOR_SIZE * remaining)

if __name__ == "__main__":
    generate_minimal_os9_disk("test_os9.dsk", 100)
    print("Created test_os9.dsk")

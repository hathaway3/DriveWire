"""
fs_repair.py - Emergency filesystem repair for DriveWire on RP2040.
Detects and resolves duplicate 'sd' folders in root that cause VFS hangs.
"""
import os

def scrub_root():
    """
    Scans the root directory for duplicate 'sd' entries.
    Renames any internal flash directory named 'sd' to 'sd_ghost' 
    to prevent VFS interference with the actual SD card mount.
    """
    print("Filesystem Repair: Scrubbing root directory...")
    try:
        # 1. Try to unmount /sd twice to be sure we are looking at flash
        for _ in range(2):
            try:
                os.umount('/sd')
                print("Unmounted /sd for repair scan.")
            except:
                pass

        # 2. Scan root for 'sd' names
        # We use a while loop because renaming might change the list
        found_ghosts = 0
        
        # MicroPython os.listdir might show duplicates, but accessing them 
        # by name usually hits the first one found.
        while True:
            root_content = os.listdir('/')
            ghosts = [x for x in root_content if x == 'sd']
            
            if not ghosts:
                break
                
            # We found at least one thing named 'sd' on flash
            ghost_name = f"sd_ghost_{found_ghosts}"
            print(f"Repair: Found flash directory 'sd'. Renaming to '{ghost_name}'...")
            try:
                os.rename('sd', ghost_name)
                found_ghosts += 1
            except Exception as e:
                print(f"Repair Error: Could not rename 'sd': {e}")
                # If we can't rename, we might try to remove it if empty
                try:
                    os.rmdir('sd')
                    print("Repair: Removed empty flash directory 'sd'.")
                except:
                    print("Repair Error: Could not remove 'sd' either. Aborting scrub.")
                    break
        
        if found_ghosts > 0:
            print(f"Filesystem Repair Complete: {found_ghosts} ghost(s) resolved.")
        else:
            print("Filesystem Repair: No root conflicts found.")
            
    except Exception as e:
        print(f"Filesystem Repair Critical Failure: {e}")

if __name__ == "__main__":
    scrub_root()

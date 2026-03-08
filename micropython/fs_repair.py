"""
fs_repair.py - Emergency filesystem repair for DriveWire on RP2040.
Detects and resolves duplicate 'sd' folders in root that cause VFS hangs.
"""
import os
import resilience

try:
    from typing import Optional, List
except ImportError:
    pass

def scrub_root():
    """
    Scans the root directory for duplicate 'sd' entries.
    Renames any internal flash directory named 'sd' to 'sd_ghost' 
    to prevent VFS interference with the actual SD card mount.
    """
    resilience.log("Filesystem Repair: Scrubbing root directory...")
    try:
        # 1. Try to unmount /sd twice to be sure we are looking at flash
        for _ in range(2):
            try:
                os.umount('/sd')
                resilience.log("Unmounted /sd for repair scan.")
            except OSError:
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
            resilience.log(f"Repair: Found flash directory 'sd'. Renaming to '{ghost_name}'...", level=2)
            try:
                os.rename('sd', ghost_name)
                found_ghosts += 1
            except Exception as e:
                resilience.log(f"Repair Error: Could not rename 'sd': {e}", level=3)
                # If we can't rename, we might try to remove it if empty
                try:
                    os.rmdir('sd')
                    resilience.log("Repair: Removed empty flash directory 'sd'.")
                except OSError:
                    resilience.log("Repair Error: Could not remove 'sd' either. Aborting scrub.", level=3)
                    break
        
        if found_ghosts > 0:
            resilience.log(f"Filesystem Repair Complete: {found_ghosts} ghost(s) resolved.")
        else:
            resilience.log("Filesystem Repair: No root conflicts found.")
            
    except Exception as e:
        resilience.log(f"Filesystem Repair Critical Failure: {e}", level=4)

if __name__ == "__main__":
    scrub_root()

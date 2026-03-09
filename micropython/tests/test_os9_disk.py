import unittest
import os
import sys
import struct
from unittest.mock import MagicMock, patch

# Mock MicroPython and project modules
sys.modules['micropython'] = MagicMock()
sys.modules['micropython'].const = lambda x: x
sys.modules['machine'] = MagicMock()
sys.modules['uasyncio'] = MagicMock()
sys.modules['utime'] = MagicMock()
sys.modules['activity_led'] = MagicMock()
sys.modules['resilience'] = MagicMock()
sys.modules['config'] = MagicMock()

# Now we can import DriveWireServer
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from drivewire import VirtualDrive, RbfParser, SECTOR_SIZE, MAX_DIR_CACHE_ENTRIES
from os9_disk_util import generate_minimal_os9_disk, create_lsn0, create_fd

class TestOS9Disk(unittest.TestCase):
    def setUp(self):
        self.test_dsk = "test_verify.dsk"
        generate_minimal_os9_disk(self.test_dsk, 100)
        self.drive = VirtualDrive(self.test_dsk)

    def tearDown(self):
        self.drive.close()
        if os.path.exists(self.test_dsk):
            os.remove(self.test_dsk)

    def test_disk_creation_validity(self):
        """Verify that the generated disk has a valid RBF structure."""
        lsn0 = self.drive.read_sector(0)
        self.assertTrue(RbfParser.is_lsn0(lsn0))
        
        root_lsn = RbfParser.get_root_dir_lsn(lsn0)
        self.assertEqual(root_lsn, 2)
        
        root_fd = self.drive.read_sector(root_lsn)
        self.assertTrue(RbfParser.is_directory_fd(root_fd))
        
        segments = RbfParser.get_segments(root_fd)
        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0][0], 3) # LSN 3 is directory body

    def test_sector_read_write_verification(self):
        """Test reading and writing data to a sector and verifying it."""
        # We'll use a sector that isn't part of the RBF metadata for this
        test_lsn = 10
        test_data = bytes([i % 256 for i in range(SECTOR_SIZE)])
        
        # Write data
        success = self.drive.write_sector(test_lsn, test_data)
        self.assertTrue(success)
        
        # Verify it's in the dirty cache (write-back)
        self.assertIn(test_lsn, self.drive.dirty_sectors)
        self.assertEqual(self.drive.dirty_sectors[test_lsn], test_data)
        
        # Read it back (should hit dirty cache)
        read_data = self.drive.read_sector(test_lsn)
        self.assertEqual(read_data, test_data)
        self.assertEqual(self.drive.stats['read_hits'], 1)
        
        # Flush to disk and clear cache to force physical read
        self.drive.flush()
        self.drive.read_cache.clear()
        
        # Read back from physical file
        read_data_physical = self.drive.read_sector(test_lsn)
        self.assertEqual(read_data_physical, test_data)
        self.assertEqual(self.drive.stats['read_misses'], 1)

    def test_rbf_awareness_and_priority_cache(self):
        """Verify RBF parser integration and sticky directory cache."""
        # 1. Read LSN 0 - identifies Root FD (LSN 2)
        self.drive.read_sector(0)
        self.assertIn(2, self.drive.dir_lsns)
        self.assertIn(0, self.drive.directory_cache)
        
        # 2. Read Root FD (LSN 2) - identifies Directory Body (LSN 3)
        self.drive.read_sector(2)
        self.assertIn(3, self.drive.dir_lsns)
        self.assertIn(2, self.drive.directory_cache)
        
        # 3. Read Directory Body (LSN 3) - should be in directory cache
        self.drive.read_sector(3)
        self.assertIn(3, self.drive.directory_cache)
        
        # Check stats
        self.assertEqual(self.drive.stats['dir_cache_misses'], 3) # 0, 2, 3 were misses initially
        
        # 4. Re-read LSN 3 - should be a directory cache hit
        self.drive.read_sector(3)
        self.assertEqual(self.drive.stats['dir_cache_hits'], 1)

    def test_cache_eviction_protection(self):
        """Verify that directory sectors are protected from LRU eviction of normal data."""
        # Populate directory cache with LSN 0 and 2
        self.drive.read_sector(0)
        self.drive.read_sector(2)
        
        # Read a bunch of non-directory sectors to fill the read_cache (limit is 8)
        for i in range(10, 20):
            self.drive.read_sector(i)
            
        # LSN 0 and 2 should still be in the directory_cache
        self.assertIn(0, self.drive.directory_cache)
        self.assertIn(2, self.drive.directory_cache)
        
        # Some early reads from 10-20 should be evicted from read_cache if it hit the limit
        # read_cache limit is 8. We read 10 sectors (10-19). 10 and 11 should be gone.
        self.assertNotIn(10, self.drive.read_cache)
        self.assertIn(19, self.drive.read_cache)

if __name__ == "__main__":
    unittest.main()

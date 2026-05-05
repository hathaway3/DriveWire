import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Centralized MicroPython mocking shim
import tests.shim as shim
shim.setup_all_mocks()

# Ensure we have a mock for os.sync which Python 3 on Windows lacks
if not hasattr(os, 'sync'):
    os.sync = lambda: None

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import AFTER shim setup
from drivewire import VirtualDrive, RbfParser, SECTOR_SIZE, MAX_DIR_CACHE_ENTRIES
from tests.os9_disk_util import generate_minimal_os9_disk, create_lsn0, create_fd

class TestOS9Disk(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        # Isolate sys.modules to prevent mock leakage during discovery
        cls.patcher = patch.dict('sys.modules', {
            'machine': MagicMock(),
            'microdot': MagicMock(),
            'activity_led': MagicMock()
        })
        cls.patcher.start()

    @classmethod
    def tearDownClass(cls):
        cls.patcher.stop()

    async def asyncSetUp(self):
        self.test_dsk = "test_verify.dsk"
        generate_minimal_os9_disk(self.test_dsk, 100)
        self.drive = VirtualDrive(self.test_dsk)

    async def asyncTearDown(self):
        if hasattr(self, 'drive') and self.drive:
            await self.drive.close()
            
        if os.path.exists(self.test_dsk):
            try:
                os.remove(self.test_dsk)
            except OSError:
                pass

    async def test_disk_creation_validity(self):
        """Verify that the generated disk has a valid RBF structure."""
        lsn0 = await self.drive.read_sector(0)
        self.assertTrue(RbfParser.is_lsn0(lsn0))
        
        root_lsn = RbfParser.get_root_dir_lsn(lsn0)
        self.assertEqual(root_lsn, 2)
        
        root_fd = await self.drive.read_sector(root_lsn)
        self.assertTrue(RbfParser.is_directory_fd(root_fd))
        
        segments = RbfParser.get_segments(root_fd)
        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0][0], 3) # LSN 3 is directory body

    async def test_sector_read_write_verification(self):
        """Test reading and writing data to a sector and verifying it."""
        test_lsn = 10
        test_data = bytes([i % 256 for i in range(SECTOR_SIZE)])
        
        # Write data
        success = await self.drive.write_sector(test_lsn, test_data)
        self.assertTrue(success)
        
        # Verify it's in the dirty cache (write-back)
        self.assertIn(test_lsn, self.drive.dirty_sectors)
        self.assertEqual(self.drive.dirty_sectors[test_lsn], test_data)
        
        # Read it back (should hit dirty cache)
        read_data = await self.drive.read_sector(test_lsn)
        self.assertEqual(read_data, test_data)
        
        # Flush to disk and clear cache to force physical read
        await self.drive.flush()
        self.drive.read_cache.clear()
        
        # Read back from physical file
        read_data_physical = await self.drive.read_sector(test_lsn)
        self.assertEqual(read_data_physical, test_data)

    async def test_rbf_awareness_and_priority_cache(self):
        """Verify RBF parser integration and sticky directory cache."""
        # Reset stats
        self.drive.stats['dir_cache_misses'] = 0
        self.drive.stats['dir_cache_hits'] = 0
        
        # 1. Read LSN 0 - identifies Root FD (LSN 2)
        await self.drive.read_sector(0)
        self.assertIn(2, self.drive.dir_lsns)
        self.assertIn(0, self.drive.directory_cache)
        
        # 2. Read Root FD (LSN 2) - identifies Directory Body (LSN 3)
        await self.drive.read_sector(2)
        self.assertIn(3, self.drive.dir_lsns)
        self.assertIn(2, self.drive.directory_cache)
        
        # 3. Read Directory Body (LSN 3) - should be in directory cache
        await self.drive.read_sector(3)
        self.assertIn(3, self.drive.directory_cache)
        
        # 4. Re-read LSN 3 - should be a directory cache hit
        await self.drive.read_sector(3)
        self.assertEqual(self.drive.stats['dir_cache_hits'], 1)

    async def test_cache_eviction_protection(self):
        """Verify that directory sectors are protected from LRU eviction of normal data."""
        # Populate directory cache with LSN 0 and 2
        await self.drive.read_sector(0)
        await self.drive.read_sector(2)
        
        # Read a bunch of non-directory sectors to fill the read_cache (limit is 8)
        for i in range(10, 20):
            await self.drive.read_sector(i)
            
        # LSN 0 and 2 should still be in the directory_cache
        self.assertIn(0, self.drive.directory_cache)
        self.assertIn(2, self.drive.directory_cache)
        
        # Check LRU eviction in read_cache (limit 8)
        # 10, 11, 12, 13, 14, 15, 16, 17, 18, 19
        # 10 and 11 should be gone.
        self.assertNotIn(10, self.drive.read_cache)
        self.assertIn(19, self.drive.read_cache)

if __name__ == '__main__':
    unittest.main()

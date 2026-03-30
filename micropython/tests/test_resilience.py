import unittest
from unittest.mock import MagicMock, patch
import os
import sys

# Simplified top-level shim import to resolve all MicroPython and host test-specific imports
import tests.shim as shim
shim.setup_all_mocks()

# Ensure we have a mock for os.sync which Python 3 on Windows lacks
if not hasattr(os, 'sync'):
    os.sync = lambda: None

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import resilience

class TestResilience(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Additional per-test-module specific mocks or overrides
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

    def setUp(self):
        # Clear log file before each test to ensure determinism
        try:
            if os.path.exists('system.log'): os.remove('system.log')
            if os.path.exists('system.log.old'): os.remove('system.log.old')
        except OSError:
            pass
        
        # Reset resilience state
        resilience.MIN_LOG_LEVEL = 1
        resilience.wdt = None

    def test_log_levels(self):
        # Explicitly set log level to DEBUG (0) for this test
        resilience.MIN_LOG_LEVEL = 0
        try:
            resilience.log("Debug message", level=0)
            resilience.log("Info message", level=1)
            resilience.log("Warn message", level=2)
            resilience.log("Error message", level=3)
            
            with open('system.log', 'r') as f:
                content = f.read()
                self.assertIn("[DEBUG] Debug message", content)
                self.assertIn("[INFO] Info message", content)
                self.assertIn("[WARN] Warn message", content)
                self.assertIn("[ERROR] Error message", content)
        finally:
            resilience.MIN_LOG_LEVEL = 1

    def test_log_rotation(self):
        # Fill log file to beyond limit (4KB default)
        with open('system.log', 'w') as f:
            f.write("A" * 5000)
            
        # Log something at level >= 1 to trigger rotation check
        resilience.log("Trigger rotation", level=1)
        
        # New file should be small (just the "Trigger rotation" line)
        with open('system.log', 'r') as f:
            content = f.read()
            self.assertLess(len(content), 1000)
            self.assertIn("Trigger rotation", content)
        
        self.assertTrue(os.path.exists('system.log.old'))

    def test_get_reset_cause(self):
        # Set constants directly on the machine object that resilience.py imported
        resilience.machine.PWRON_RESET = 1
        resilience.machine.WDT_RESET = 3
        # Patch reset_cause return on the same resilience.machine reference
        with patch.object(resilience.machine, 'reset_cause', return_value=1):
            self.assertEqual(resilience.get_reset_cause(), "Power-On")
            
        with patch.object(resilience.machine, 'reset_cause', return_value=3):
            self.assertEqual(resilience.get_reset_cause(), "Watchdog Reset")

    def test_watchdog(self):
        mock_wdt = MagicMock()
        with patch('resilience.machine.WDT', return_value=mock_wdt):
            # Also mock the log function to avoid output
            with patch('resilience.log'):
                wdt = resilience.init_wdt(1000)
                self.assertIsInstance(wdt, resilience.SafeWatchdog)
                # SafeWatchdog.feed should call machine.wdt.feed
                wdt.feed()
                mock_wdt.feed.assert_called_once()

    def test_collect_garbage(self):
        with patch('resilience.gc.collect') as mock_collect:
            resilience.collect_garbage("testing")
            mock_collect.assert_called()

    def test_feed_wdt_with_active_watchdog(self):
        """feed_wdt() should call wdt.feed() when watchdog is initialized."""
        mock_safe_wdt = MagicMock()
        old_wdt = resilience.wdt
        try:
            resilience.wdt = mock_safe_wdt
            resilience.feed_wdt()
            mock_safe_wdt.feed.assert_called_once()
        finally:
            resilience.wdt = old_wdt

    def test_feed_wdt_without_watchdog(self):
        """feed_wdt() should not raise when wdt is None."""
        old_wdt = resilience.wdt
        try:
            resilience.wdt = None
            resilience.feed_wdt()  # Should not raise
        finally:
            resilience.wdt = old_wdt

if __name__ == '__main__':
    unittest.main()

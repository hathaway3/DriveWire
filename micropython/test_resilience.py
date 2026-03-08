import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Mock MicroPython modules
sys.modules['machine'] = MagicMock()
sys.modules['microdot_asyncio'] = MagicMock()
sys.modules['microdot'] = MagicMock()
sys.modules['syslog'] = MagicMock()
sys.modules['activity_led'] = MagicMock()

# Mock os.sync which is missing on standard Python
if not hasattr(os, 'sync'):
    os.sync = lambda: None

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import resilience

class TestResilience(unittest.TestCase):
    def setUp(self):
        # Clear log file before each test
        try:
            os.remove('system.log')
        except OSError:
            pass

    def test_log_levels(self):
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

    def test_log_rotation(self):
        # Fill log file to beyond limit (4KB)
        with open('system.log', 'w') as f:
            f.write("A" * 5000)
            
        resilience.log("Trigger rotation", level=1)
        
        # In our implementation, if stats[6] > MAX_LOG_SIZE, it renames to .old
        # and starts a new LOG_FILE.
        with open('system.log', 'r') as f:
            content = f.read()
            # New file should be small (just the "Trigger rotation" line)
            self.assertLess(len(content), 1000)
            self.assertIn("Trigger rotation", content)
        
        self.assertTrue(os.path.exists('system.log.old'))

    def test_get_reset_cause(self):
        import machine
        machine.PWRON_RESET = 1
        machine.WDT_RESET = 3
        with patch('machine.reset_cause', return_value=1):
            self.assertEqual(resilience.get_reset_cause(), "Power-On")
        with patch('machine.reset_cause', return_value=3):
            self.assertEqual(resilience.get_reset_cause(), "Watchdog Reset")

    def test_watchdog(self):
        mock_wdt = MagicMock()
        with patch('machine.WDT', return_value=mock_wdt):
            wdt = resilience.init_wdt(1000)
            self.assertIsInstance(wdt, resilience.SafeWatchdog)
            wdt.feed()
            mock_wdt.feed.assert_called_once()

    def test_collect_garbage(self):
        import gc
        with patch('gc.collect') as mock_collect:
            resilience.collect_garbage("testing")
            mock_collect.assert_called()

    def test_feed_wdt_with_active_watchdog(self):
        """feed_wdt() should call wdt.feed() when watchdog is initialized."""
        mock_wdt_instance = MagicMock()
        mock_safe_wdt = MagicMock()
        mock_safe_wdt.feed = MagicMock()
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

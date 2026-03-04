import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Mock MicroPython modules
sys.modules['machine'] = MagicMock()
sys.modules['microdot_asyncio'] = MagicMock()
sys.modules['microdot'] = MagicMock()

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
        # Fill log file to near limit
        with open('system.log', 'w') as f:
            f.write("A" * 15000)
            
        resilience.log("Trigger rotation", level=1)
        
        with open('system.log', 'r') as f:
            content = f.read()
            self.assertLess(len(content), 1000)
            self.assertIn("Trigger rotation", content)

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

if __name__ == '__main__':
    unittest.main()

# boot.py -- run on boot-up
import lib_installer
import config
import gc

# Report memory status
gc.collect()
print(f"Free memory at boot: {gc.mem_free()} bytes")

# Connect to WiFi
wifi_ssid = config.shared_config.get('wifi_ssid')
wifi_password = config.shared_config.get('wifi_password')

if wifi_ssid and wifi_ssid != 'YOUR_SSID':
    try:
        lib_installer.connect_wifi(wifi_ssid, wifi_password)
    except Exception as e:
        print(f"WiFi Connection failed: {e}")

# Ensure required libraries are installed (e.g., microdot, sdcard)
# This connects to WiFi using credentials from config if needed.
try:
    lib_installer.install_dependencies()
except Exception as e:
    print(f"Skipping auto-install: {e}")
    # Log to file for headless debugging
    try:
        with open("boot_error.log", "a") as f:
            f.write(f"Lib install error: {e}\n")
    except OSError:
        pass

# Mount SD card (best effort — follows library installation)
try:
    import sd_card
    sd_card.init_sd()
except Exception as e:
    print(f"SD card init skipped or failed: {e}")
    # Log to file for headless debugging
    try:
        with open("boot_error.log", "a") as f:
            f.write(f"Boot error: {e}\n")
    except OSError:
        pass


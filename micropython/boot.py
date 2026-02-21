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

# Mount SD card (best effort — continues without it)
try:
    import sd_card
    sd_card.init_sd()
except Exception as e:
    print(f"SD card init skipped: {e}")

# Ensure libraries are installed
try:
    lib_installer.install_dependencies()
except Exception as e:
    print(f"Skipping auto-install: {e}")
    # Log to file for headless debugging
    try:
        with open("boot_error.log", "a") as f:
            f.write(f"Boot error: {e}\n")
    except OSError:
        pass


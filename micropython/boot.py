import lib_installer
import config
import gc
import fs_repair
import time
import machine
import resilience

# Give USB power delivery time to stabilize on headless boot
resilience.log(f"DriveWire booting. Reset cause: {resilience.get_reset_cause()}")
resilience.log("Powering on... Waiting for voltage stabilization.")
time.sleep(2)
resilience.init_wdt(timeout_ms=8000)

try:
    # Scrub root filesystem for conflicts (duplicate sd folders)
    try:
        fs_repair.scrub_root()
    except Exception as e:
        resilience.log(f"FS Scrub failed: {e}", level=2)

    # Report memory status
    resilience.collect_garbage("boot_start")
    resilience.log(f"Free memory at boot: {gc.mem_free()} bytes")
    
    # Connect to WiFi with retry mechanism
    wifi_ssid = config.shared_config.get('wifi_ssid')
    wifi_password = config.shared_config.get('wifi_password')
    
    if wifi_ssid and wifi_ssid != 'YOUR_SSID':
        retry_count = 0
        max_retries = 3
        backoff = 2
        while retry_count < max_retries:
            try:
                resilience.log(f"Connecting to WiFi '{wifi_ssid}' (Attempt {retry_count + 1})...")
                lib_installer.connect_wifi(wifi_ssid, wifi_password)
                resilience.log("WiFi Connected successfully.")
                break
            except (OSError, RuntimeError) as e:
                retry_count += 1
                if retry_count >= max_retries:
                    resilience.log(f"WiFi Connection failed after {max_retries} attempts: {e}", level=3)
                else:
                    sleep_time = backoff ** retry_count
                    resilience.log(f"WiFi error: {e}. Retrying in {sleep_time}s...", level=2)
                    resilience.feed_wdt()
                    time.sleep(min(sleep_time, 6))  # Cap to stay within WDT window
                    resilience.feed_wdt()

    # Ensure required libraries are installed
    resilience.feed_wdt()
    try:
        lib_installer.install_dependencies()
    except Exception as e:
        resilience.log(f"Skipping auto-install: {e}", level=2)
    resilience.feed_wdt()
    
    # Mount SD card (best effort)
    try:
        import sd_card
        if not sd_card.init_sd():
            resilience.log("SD card mount unsuccessful (expected if no card).", level=2)
    except Exception as e:
        resilience.log(f"SD card init failed: {e}", level=3)
    resilience.feed_wdt()

except Exception as fatal_e:
    resilience.log(f"Fatal boot crash: {fatal_e}", level=4)
    resilience.log("Rebooting in 10 seconds...", level=4)
    time.sleep(10)
    machine.reset()


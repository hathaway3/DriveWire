import network
import time
import os
import resilience

try:
    from typing import Optional, List, Dict, Any, Tuple
except ImportError:
    pass

def connect_wifi(ssid, password, max_retries=3):
    """Connect to WiFi with retry logic."""
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    
    for attempt in range(max_retries):
        if wlan.isconnected():
            resilience.log(f'Already connected: {wlan.ifconfig()}')
            return True
            
        resilience.log(f'Connecting to network (attempt {attempt + 1}/{max_retries})...')
        wlan.connect(ssid, password)
        
        timeout = 10
        while not wlan.isconnected() and timeout > 0:
            time.sleep(1)
            timeout -= 1
        
        if wlan.isconnected():
            resilience.log(f'Network config: {wlan.ifconfig()}')
            return True
        else:
            resilience.log(f'Connection attempt {attempt + 1} failed', level=2)
    
    resilience.log('WiFi connection failed after all retries', level=3)
    return False

def install_dependencies():
    """Install required dependencies with retry logic and verification."""
    # List of (module_name, pip_name, [github_files])
    # pip_name is used for mip.install()
    # github_files is used for manual fallback if mip fails
    dependencies = [
        ("microdot", "microdot", {
            "name": "Microdot",
            "base": "https://raw.githubusercontent.com/miguelgrinberg/microdot/v1.3.4/src",
            "files": ["microdot.py", "microdot_asyncio.py"]
        }),
        ("sdcard", "sdcard", {
            "name": "SD Card Driver",
            "base": "https://raw.githubusercontent.com/micropython/micropython-lib/master/micropython/drivers/storage/sdcard",
            "files": ["sdcard.py"]
        })
    ]

    for module_name, pip_name, github_info in dependencies:
        try:
            __import__(module_name)
            resilience.log(f"{module_name} library already installed.")
        except ImportError:
            resilience.log(f"{module_name} library not found. Attempting to install...")
            
            # Load config for WiFi credentials if not already connected
            try:
                from config import Config
                cfg = Config()
            except ImportError:
                resilience.log("Config not found, cannot connect to WiFi.", level=3)
                return

            if not connect_wifi(cfg.get("wifi_ssid"), cfg.get("wifi_password")):
                resilience.log(f"Cannot install {module_name}: No WiFi connection.", level=3)
                continue
                
            try:
                # Try mip (standard on newer MicroPython)
                try:
                    import mip
                    resilience.log(f"Using mip to install {pip_name}...")
                    mip.install(pip_name)
                    resilience.feed_wdt()
                    # Verify installation
                    __import__(module_name)
                    resilience.log(f"Installation of {module_name} complete via mip.")
                    continue
                except (AttributeError, ImportError, Exception) as e:
                    resilience.log(f"mip install failed for {pip_name}: {e}. Trying github fallback...", level=2)

                # Fallback to manual download using raw sockets (memory-safe streaming)
                try:
                    resilience.log(f"Attempting manual install for {github_info['name']}...")
                    success = True
                    for file in github_info['files']:
                        resilience.log(f"Downloading {file}...")
                        url = f"{github_info['base']}/{file}"
                        
                        try:
                            # Use memory-safe stream instead of urequests
                            sock = resilience.open_remote_stream(url)
                            if not sock:
                                resilience.log(f"Failed to open stream for {file}", level=2)
                                success = False
                                break
                                
                            try:
                                with open(file, "w") as f:
                                    while True:
                                        chunk = sock.recv(512)
                                        if not chunk:
                                            break
                                        f.write(chunk.decode('utf-8', 'ignore'))
                                        resilience.feed_wdt()
                                resilience.log(f"Saved {file}")
                            finally:
                                sock.close()
                                
                        except Exception as e:
                            resilience.log(f"Download error for {file}: {e}", level=3)
                            success = False
                            break
                    
                    if success:
                        # Verify installation
                        try:
                            __import__(module_name)
                            resilience.log(f"Installation of {module_name} verified.")
                        except ImportError:
                            resilience.log(f"Warning: {module_name} installed but import failed.", level=2)
                    else:
                        resilience.log(f"Failed to install {github_info['name']} from GitHub.", level=3)

                except Exception as e:
                    resilience.log(f"Manual download failed: {e}", level=3)
                    resilience.log(f"Please manually copy the files for {module_name} to the device.", level=3)

            except Exception as e:
                resilience.log(f"Failed to install {module_name}: {e}", level=3)

if __name__ == "__main__":
    install_dependencies()

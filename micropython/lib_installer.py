import network
import time
import os

def connect_wifi(ssid, password, max_retries=3):
    """Connect to WiFi with retry logic."""
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    
    for attempt in range(max_retries):
        if wlan.isconnected():
            print('Already connected:', wlan.ifconfig())
            return True
            
        print(f'Connecting to network (attempt {attempt + 1}/{max_retries})...')
        wlan.connect(ssid, password)
        
        timeout = 10
        while not wlan.isconnected() and timeout > 0:
            time.sleep(1)
            timeout -= 1
        
        if wlan.isconnected():
            print('Network config:', wlan.ifconfig())
            return True
        else:
            print(f'Connection attempt {attempt + 1} failed')
    
    print('WiFi connection failed after all retries')
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
            print(f"{module_name} library already installed.")
        except ImportError:
            print(f"{module_name} library not found. Attempting to install...")
            
            # Load config for WiFi credentials if not already connected
            try:
                from config import Config
                cfg = Config()
            except ImportError:
                print("Config not found, cannot connect to WiFi.")
                return

            if not connect_wifi(cfg.get("wifi_ssid"), cfg.get("wifi_password")):
                print(f"Cannot install {module_name}: No WiFi connection.")
                continue
                
            try:
                # Try mip (standard on newer MicroPython)
                try:
                    import mip
                    print(f"Using mip to install {pip_name}...")
                    mip.install(pip_name)
                    # Verify installation
                    __import__(module_name)
                    print(f"Installation of {module_name} complete via mip.")
                    continue
                except (AttributeError, ImportError, Exception) as e:
                    print(f"mip install failed for {pip_name}: {e}. Trying github fallback...")

                # Fallback to manual download using urequests
                try:
                    import urequests
                    
                    print(f"Attempting manual install for {github_info['name']}...")
                    success = True
                    for file in github_info['files']:
                        print(f"Downloading {file}...")
                        url = f"{github_info['base']}/{file}"
                        try:
                            r = urequests.get(url)
                            try:
                                if r.status_code == 200:
                                    with open(file, "w") as f:
                                        f.write(r.text)
                                    print(f"Saved {file}")
                                else:
                                    print(f"Failed to download {file} (Status {r.status_code})")
                                    success = False
                            finally:
                                r.close()
                        except Exception as e:
                            print(f"Download error: {e}")
                            success = False
                        
                        if not success:
                            break
                    
                    if success:
                        # Verify installation
                        try:
                            __import__(module_name)
                            print(f"Installation of {module_name} verified.")
                        except ImportError:
                            print(f"Warning: {module_name} installed but import failed.")
                    else:
                        print(f"Failed to install {github_info['name']} from GitHub.")

                except Exception as e:
                    print(f"Manual download failed: {e}")
                    print(f"Please manually copy the files for {module_name} to the device.")

            except Exception as e:
                print(f"Failed to install {module_name}: {e}")

if __name__ == "__main__":
    install_dependencies()

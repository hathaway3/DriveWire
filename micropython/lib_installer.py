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
    try:
        import microdot
        print("Microdot library already installed.")
        return
    except ImportError:
        print("Microdot library not found. Attempting to install...")
        
        # Load config for WiFi credentials
        try:
            from config import Config
            cfg = Config()
        except ImportError:
            print("Config not found, cannot connect to WiFi.")
            return

        if not connect_wifi(cfg.get("wifi_ssid"), cfg.get("wifi_password")):
            print("Cannot install libraries: No WiFi connection.")
            return
            
        try:
            # Try mip (standard on newer MicroPython)
            try:
                import mip
                print("Using mip to install microdot...")
                try:
                    mip.install("microdot")
                except Exception:
                    # Fallback to direct github install
                    mip.install('github:miguelgrinberg/microdot')

                # Verify installation
                import microdot
                print("Installation complete via mip.")
                return
            except (ImportError, Exception) as e:
                print(f"mip install failed or incomplete: {e}")

            # Fallback to manual download using urequests
            try:
                import urequests
                
                candidates = [
                    {
                        "name": "v2 (latest)",
                        "base": "https://raw.githubusercontent.com/miguelgrinberg/microdot/main/src/microdot",
                        "files": ["microdot.py", "microdot_asyncio.py"] 
                    },
                    {
                        "name": "v1.3.4 (stable)",
                        "base": "https://raw.githubusercontent.com/miguelgrinberg/microdot/v1.3.4/src",
                        "files": ["microdot.py", "microdot_asyncio.py"]
                    }
                ]

                installed = False
                for cand in candidates:
                    print(f"Attempting install from {cand['name']}...")
                    success = True
                    for file in cand['files']:
                        print(f"Downloading {file}...")
                        url = f"{cand['base']}/{file}"
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
                        installed = True
                        print(f"Installation successful from {cand['name']}.")
                        # Verify installation
                        try:
                            import microdot
                            print("Installation verified.")
                        except ImportError:
                            print("Warning: Installation completed but import failed.")
                        break
                    else:
                        print(f"Failed to install from {cand['name']}. Trying next...")

                if not installed:
                    raise Exception("All download attempts failed.")

            except Exception as e:
                print(f"Manual download failed: {e}")
                print("Please manually copy 'microdot.py' and 'microdot_asyncio.py' to the device.")

        except Exception as e:
            print(f"Failed to install libraries: {e}")

if __name__ == "__main__":
    install_dependencies()

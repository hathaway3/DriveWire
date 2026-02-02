import network
import time
import os

def connect_wifi(ssid, password):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print('connecting to network...')
        wlan.connect(ssid, password)
        timeout = 10
        while not wlan.isconnected() and timeout > 0:
            time.sleep(1)
            timeout -= 1
    
    if wlan.isconnected():
        print('network config:', wlan.ifconfig())
        return True
    else:
        print('Wifi connect failed')
        return False

def install_dependencies():
    try:
        import microdot
        print("Microdot library already installed.")
    except ImportError:
        print("Microdot library not found. Attempting to install...")
        
        # We need wifi to install
        try:
            from config import Config
            cfg = Config()
        except ImportError:
            print("Config not found, cannot connect to WiFi.")
            return

        if connect_wifi(cfg.get("wifi_ssid"), cfg.get("wifi_password")):
             try:
                # Try mip (standard on newer MicroPython)
                try:
                    import mip
                    print("Using mip to install microdot...")
                    # Try installing the package by name first (if in micropython-lib)
                    try:
                        mip.install("microdot")
                    except Exception:
                        # Fallback to direct github install
                        # Note: newer microdot structure might be different
                        mip.install('github:miguelgrinberg/microdot') 
                        # If that installs the whole repo it might vary.
                        # Let's try installing exact files from 'v2' branch which is stable API for now?
                        # Actually, let's just stick to manual download fallback which is safer control.
                        pass

                    # Check if actually installed?
                    import microdot
                    print("Installation complete via mip.")
                    return
                except (ImportError, Exception) as e:
                    print(f"mip install failed or incomplete: {e}")

                # Fallback to manual download using urequests
                try:
                     import urequests
                     
                     # Candidate URLs. Try v2 structure (package style) then v1 (flat style)
                     # v2: src/microdot/microdot.py
                     # v1: src/microdot.py (tag v1.3.4)
                     
                     candidates = [
                        {
                            "name": "v2 (latest)",
                            "base": "https://raw.githubusercontent.com/miguelgrinberg/microdot/main/src/microdot",
                            "files": ["microdot.py", "microdot_asyncio.py"] 
                            # Note: in v2 asyncio might be part of the package. 
                            # If this fails, we fall back to v1 which is safer for this simple script.
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
                                 if r.status_code == 200:
                                     with open(file, "w") as f:
                                         f.write(r.text)
                                     print(f"Saved {file}")
                                 else:
                                     print(f"Failed to download {file} (Status {r.status_code})")
                                     success = False
                                 r.close()
                             except Exception as e:
                                 print(f"Download error: {e}")
                                 success = False
                             
                             if not success: break
                        
                         if success:
                             installed = True
                             print(f"Installation successful from {cand['name']}.")
                             break
                         else:
                             print(f"Failed to install from {cand['name']}. Trying next...")

                     if not installed:
                         raise Exception("All download attempts failed.")

                except Exception as e:
                     print(f"Manual download failed: {e}")
                     print("Please manually copy 'microdot.py' and 'microdot_asyncio.py' to the device.")
                except Exception as e:
                     print(f"Manual download failed: {e}")
                     print("Please manually copy 'microdot.py' and 'microdot_asyncio.py' to the device.")

             except Exception as e:
                 print(f"Failed to install libraries: {e}")
        else:
            print("Cannot install libraries: No WiFi connection.")

if __name__ == "__main__":
    install_dependencies()

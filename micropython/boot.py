# boot.py -- run on boot-up
import lib_installer
import config
import gc

# Report memory status
gc.collect()
print(f"Free memory at boot: {gc.mem_free()} bytes")

# Ensure libraries are installed
try:
    lib_installer.install_dependencies()
except Exception as e:
    print(f"Skipping auto-install: {e}")
    # Log to file for headless debugging
    try:
        with open("boot_error.log", "a") as f:
            f.write(f"Boot error: {e}\n")
    except:
        pass

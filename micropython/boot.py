# boot.py -- run on boot-up
import lib_installer
import config

# Ensure libraries are installed
try:
    lib_installer.install_dependencies()
except Exception as e:
    print(f"Skipping auto-install: {e}")

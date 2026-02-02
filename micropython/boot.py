# boot.py -- run on boot-up
import lib_installer
import config

# Ensure libraries are installed
lib_installer.install_dependencies()

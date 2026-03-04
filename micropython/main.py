import uasyncio as asyncio
from drivewire import DriveWireServer
from web_server import app
import time_sync
import gc
import machine
import resilience
import time

# Safety delay for development (allows interrupting boot loops)
time.sleep(2)

async def main():
    resilience.log("Initializing DriveWire Server...")
    
    # Initialize Watchdog
    wdt = resilience.init_wdt(timeout_ms=15000) # 15s timeout for heavy I/O
    
    # Configure GC to run aggressively early
    gc.threshold(50000)
    resilience.collect_garbage("server_start")
    resilience.log(f"Free memory: {gc.mem_free()} bytes")
    
    # Sync time on startup (best effort)
    try:
        time_sync.sync_time()
    except Exception as e:
        resilience.log(f"Initial time sync failed: {e}", level=2)
    
    # Start background task to keep system time synced every 12 hours
    asyncio.create_task(time_sync.keep_time_synced(interval_hours=12))
    
    # Instantiate the DriveWire Server
    dw_server = DriveWireServer()
    
    # Attach to web app for dynamic reloading
    app.dw_server = dw_server
    
    # Create the DriveWire task
    asyncio.create_task(dw_server.run())
    
    resilience.log("Starting Web Server on port 80...")
    
    # Background task to feed the watchdog
    async def watchdog_feeder():
        while True:
            wdt.feed()
            await asyncio.sleep(5)
    
    asyncio.create_task(watchdog_feeder())
    
    # Start the Web Server (this will keep running)
    await app.start_server(port=80, debug=True)

# Entry Point
try:
    asyncio.run(main())
except KeyboardInterrupt:
    resilience.log("Server stopped by user.")
except Exception as e:
    resilience.log(f"Unexpected server crash: {e}", level=4)
    resilience.log("Rebooting in 10 seconds to recover...", level=4)
    time.sleep(10)
    machine.reset()

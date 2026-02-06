import uasyncio as asyncio
from drivewire import DriveWireServer
from web_server import app
import time_sync
import gc

async def main():
    print("Initializing DriveWire Server...")
    
    # Report memory status
    gc.collect()
    print(f"Free memory: {gc.mem_free()} bytes")
    
    # Sync time on startup (best effort)
    time_sync.sync_time()
    
    # Instantiate the DriveWire Server
    dw_server = DriveWireServer()
    
    # Attach to web app for dynamic reloading
    app.dw_server = dw_server
    
    # Create the DriveWire task
    asyncio.create_task(dw_server.run())
    
    print("Starting Web Server on port 80...")
    # Start the Web Server (this will keep running)
    await app.start_server(port=80, debug=True)

# Entry Point
try:
    asyncio.run(main())
except KeyboardInterrupt:
    print("Server stopped by user.")
except Exception as e:
    # Log to file for headless debugging
    try:
        with open("error.log", "a") as f:
            import time
            f.write(f"[{time.localtime()}] Startup error: {e}\n")
    except:
        pass
    print(f"Unexpected error: {e}")

import uasyncio as asyncio
from drivewire import DriveWireServer
from web_server import app
import time_sync

async def main():
    print("Initializing DriveWire Server...")
    
    # Sync time on startup (best effort)
    time_sync.sync_time()
    
    # Instantiate the DriveWire Server
    dw_server = DriveWireServer()
    
    # Attach to web app for dynamic reloading
    app.dw_server = dw_server
    
    # Create the DriveWire task
    asyncio.create_task(dw_server.run())
    
    print("Starting Web Server on port 80...")
    # Start the Web Server. 
    # start_server is a coroutine that will keep running.
    await app.start_server(port=80, debug=True)

# Entry Point
try:
    asyncio.run(main())
except KeyboardInterrupt:
    print("Server stopped.")
except Exception as e:
    # Optional: Log to file for headless debugging
    with open("error.log", "a") as f:
        f.write(f"Startup error: {e}\n")
    print(f"Unexpected error: {e}")

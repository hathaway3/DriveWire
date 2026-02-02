try:
    from microdot_asyncio import Microdot, Response, send_file
except ImportError:
    # Fallback for checking installation
    try:
        from microdot import Microdot, Response, send_file
    except ImportError:
        print("Microdot not installed.")
        raise

from config import shared_config
import json
import os

app = Microdot()
config = shared_config

@app.route('/')
async def index(request):
    return send_file('www/index.html')

@app.route('/static/<path:path>')
async def static(request, path):
    if '..' in path:
        return 'Not found', 404
    return send_file('www/static/' + path)

@app.route('/api/config', methods=['GET', 'POST'])
async def config_endpoint(request):
    if request.method == 'GET':
        return config.config
    
    elif request.method == 'POST':
        try:
            new_config = request.json
            
            if 'baud_rate' in new_config:
                config.set('baud_rate', new_config['baud_rate'])
            if 'wifi_ssid' in new_config:
                config.set('wifi_ssid', new_config['wifi_ssid'])
            if 'wifi_password' in new_config:
                config.set('wifi_password', new_config['wifi_password'])
            if 'ntp_server' in new_config:
                config.set('ntp_server', new_config['ntp_server'])
            if 'timezone_offset' in new_config:
                config.set('timezone_offset', new_config['timezone_offset'])
            if 'serial_map' in new_config:
                config.set('serial_map', new_config['serial_map'])
            if 'drives' in new_config:
                drives = new_config['drives']
                if isinstance(drives, list) and len(drives) == 4:
                    config.set('drives', drives)
            
            # Trigger reload on DriveWire Server if attached
            if hasattr(app, 'dw_server'):
                print("Reloading DriveWire Config...")
                app.dw_server.reload_config()

            return {'status': 'ok'}
            return {'status': 'ok'}
        except Exception as e:
            print(f"Error saving config: {e}")
            return {'status': 'error', 'message': str(e)}, 500

def get_dsk_files():
    files = []
    # Check root
    try:
        for f in os.listdir('/'):
            if f.lower().endswith('.dsk'):
                files.append('/' + f)
    except Exception: pass
    
    # Check SD
    try:
        for f in os.listdir('/sd'):
            if f.lower().endswith('.dsk'):
                files.append('/sd/' + f)
    except Exception: pass
    
    files.sort()
    return files

@app.route('/api/files')
async def files_endpoint(request):
    return get_dsk_files()

@app.route('/api/status')
async def status_endpoint(request):
    if hasattr(app, 'dw_server'):
        return {
            'stats': app.dw_server.stats,
            'logs': list(app.dw_server.log_buffer),
            'term_buf': list(app.dw_server.terminal_buffer),
            'monitor_chan': app.dw_server.monitor_channel
        }
    return {'error': 'DriveWire Server not attached'}

@app.route('/api/serial/monitor', methods=['POST'])
async def monitor_chan_endpoint(request):
    if hasattr(app, 'dw_server'):
        chan = request.json.get('chan', -1)
        app.dw_server.monitor_channel = int(chan)
        app.dw_server.terminal_buffer = bytearray() # Clear on change
        return {'status': 'ok'}
    return {'error': 'DriveWire Server not attached'}, 500

def start():
    print("Starting Web Server...")
    app.run(port=80, debug=True)


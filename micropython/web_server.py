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
    try:
        return send_file('www/index.html')
    except OSError:
        return 'Not found', 404

@app.route('/static/<path:path>')
async def static(request, path):
    if '..' in path:
        return 'Not found', 404
    try:
        return send_file('www/static/' + path)
    except OSError:
        return 'Not found', 404

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
            # SD card SPI pin config
            for sd_key in ('sd_spi_id', 'sd_sck', 'sd_mosi', 'sd_miso', 'sd_cs', 'sd_mount_point'):
                if sd_key in new_config:
                    config.set(sd_key, new_config[sd_key])
            
            # Trigger reload on DriveWire Server if attached
            if hasattr(app, 'dw_server'):
                print("Reloading DriveWire Config...")
                app.dw_server.reload_config()

            return {'status': 'ok'}
        except Exception as e:
            print(f"Error saving config: {e}")
            return {'status': 'error', 'message': str(e)}, 500

def _scan_dsk_dir(base_path, depth=0, max_depth=1):
    """Recursively scan a directory for .dsk files up to max_depth levels deep."""
    results = []
    try:
        for entry in os.listdir(base_path):
            full_path = base_path.rstrip('/') + '/' + entry
            if entry.lower().endswith('.dsk'):
                results.append(full_path)
            elif depth < max_depth:
                # Check if it's a directory by trying to list it
                try:
                    os.listdir(full_path)
                    results.extend(_scan_dsk_dir(full_path, depth + 1, max_depth))
                except OSError:
                    pass  # Not a directory or inaccessible
    except OSError:
        pass  # Directory doesn't exist or inaccessible
    return results


def get_dsk_files():
    """Find all .dsk files on internal flash and SD card storage."""
    files = []
    # Scan internal flash root (1 level deep)
    files.extend(_scan_dsk_dir('/', max_depth=1))
    # Scan SD card if mounted (1 level deep)
    files.extend(_scan_dsk_dir('/sd', max_depth=1))
    # Remove duplicates (in case /sd is inside /)
    seen = set()
    unique = []
    for f in files:
        if f not in seen:
            seen.add(f)
            unique.append(f)
    unique.sort()
    return unique


@app.route('/api/files')
async def files_endpoint(request):
    return get_dsk_files()


@app.route('/api/sd/status')
async def sd_status_endpoint(request):
    """Return SD card mount status and storage info."""
    try:
        import sd_card
        info = sd_card.get_info()
        info['files_found'] = len([f for f in get_dsk_files() if f.startswith('/sd')])
        return info
    except ImportError:
        return {'mounted': False, 'mount_point': '/sd', 'error': 'sd_card module not available'}
    except Exception as e:
        return {'mounted': False, 'error': str(e)}

@app.route('/api/status')
async def status_endpoint(request):
    try:
        if hasattr(app, 'dw_server'):
            drive_stats = []
            for d in app.dw_server.drives:
                if d:
                    ds = d.stats.copy()
                    ds['filename'] = d.filename.split('/')[-1]
                    ds['dirty_count'] = len(d.dirty_sectors)
                    drive_stats.append(ds)
                else:
                    drive_stats.append(None)
                    
            return {
                'stats': app.dw_server.stats,
                'logs': list(app.dw_server.log_buffer),
                'term_buf': list(app.dw_server.terminal_buffer),
                'monitor_chan': app.dw_server.monitor_channel,
                'drive_stats': drive_stats
            }
        return {'error': 'DriveWire Server not attached'}
    except Exception as e:
        return {'error': f'Status error: {e}'}, 500

@app.route('/api/serial/monitor', methods=['POST'])
async def monitor_chan_endpoint(request):
    if hasattr(app, 'dw_server'):
        try:
            body = request.json
            if not body:
                return {'error': 'Invalid JSON body'}, 400
            chan = body.get('chan', -1)
            app.dw_server.monitor_channel = int(chan)
            app.dw_server.terminal_buffer = bytearray() # Clear on change
            return {'status': 'ok'}
        except (ValueError, TypeError) as e:
            return {'error': f'Invalid channel: {e}'}, 400
    return {'error': 'DriveWire Server not attached'}, 500

def start():
    print("Starting Web Server...")
    app.run(port=80, debug=True)


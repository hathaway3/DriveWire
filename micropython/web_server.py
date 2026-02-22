try:
    from microdot_asyncio import Microdot, Response, Request, send_file
except ImportError:
    # Fallback for checking installation
    try:
        from microdot import Microdot, Response, Request, send_file
    except ImportError:
        print("Microdot not installed.")
        raise

from config import shared_config
import json
import os

app = Microdot()
# Microdot 1.3.4 uses Request class attributes for limits
Request.max_content_length = 2 * 1024 * 1024  # 2MB limit for uploads
Request.max_body_length = 16 * 1024          # Small body limit to force streaming
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
        # Always include server time (lightweight)
        try:
            import time_sync
            t = time_sync.get_local_time()
            server_time = f"{t[0]:04d}-{t[1]:02d}-{t[2]:02d} {t[3]:02d}:{t[4]:02d}:{t[5]:02d}"
        except Exception:
            server_time = "--:--:--"

        if hasattr(app, 'dw_server'):
            drive_stats = []
            for d in app.dw_server.drives:
                if d:
                    ds = d.stats.copy()
                    ds['filename'] = d.filename.split('/')[-1]
                    ds['full_path'] = d.filename
                    ds['dirty_count'] = len(d.dirty_sectors)
                    drive_stats.append(ds)
                else:
                    drive_stats.append(None)
                    
            return {
                'server_time': server_time,
                'stats': app.dw_server.stats,
                'logs': list(app.dw_server.log_buffer),
                'term_buf': list(app.dw_server.terminal_buffer),
                'monitor_chan': app.dw_server.monitor_channel,
                'drive_stats': drive_stats
            }
        return {'server_time': server_time, 'error': 'DriveWire Server not attached'}
    except Exception as e:
        return {'error': f'Status error: {e}'}, 500

@app.route('/api/files/delete', methods=['POST'])
async def delete_file_endpoint(request):
    """Delete a file if not currently mounted."""
    try:
        if not hasattr(app, 'dw_server'):
            return {'error': 'DriveWire Server not attached'}, 500
            
        body = request.json
        if not body or 'path' not in body:
            return {'error': 'Missing file path'}, 400
            
        path = body['path']
        
        # Security: only allow deleting from /sd or non-system files
        if not path.startswith('/sd/') and not path.endswith('.dsk'):
            return {'error': 'Access denied: Cannot delete system files'}, 403
            
        # Check if mounted
        for i, drive in enumerate(app.dw_server.drives):
            if drive and drive.filename == path:
                return {'error': f'Cannot delete: File is mounted in DRIVE {i}'}, 400
                
        # Attempt delete
        try:
            os.remove(path)
            return {'status': 'ok'}
        except OSError as e:
            return {'error': f'Delete failed: {e}'}, 500
            
    except Exception as e:
        return {'error': f'Delete error: {e}'}, 500

@app.errorhandler(413)
async def request_too_large(request):
    print(f"413 Error: Request too large. Content-Length: {request.headers.get('Content-Length')}")
    return {'error': 'Request too large. Max size is 2MB.'}, 413

@app.route('/api/files/upload', methods=['POST'])
async def upload_file_endpoint(request):
    """Handle file upload via streaming POST with X-Filename header."""
    try:
        filename = request.headers.get('X-Filename')
        content_length = request.headers.get('Content-Length')
        print(f"Upload starting: {filename} (Content-Length: {content_length})")
        
        if not filename:
            return {'error': 'Missing X-Filename header. Please use the Files tab drag-and-drop.'}, 400
            
        # Basic validation
        if not filename.lower().endswith('.dsk'):
            return {'error': 'Only .dsk files are supported.'}, 400
            
        # Clean filename to prevent path traversal
        clean_name = filename.split('/')[-1].split('\\')[-1]
        target_path = '/sd/' + clean_name
        
        # Ensure /sd exists
        try:
            if '/sd' not in os.listdir('/'):
                return {'error': 'SD card not mounted. Cannot upload to SD.'}, 400
        except Exception:
            return {'error': 'SD card check failed.'}, 500

        # Stream save to avoid memory issues
        # We read from request.stream in 4KB chunks
        chunk_size = 4096
        bytes_written = 0
        
        try:
            with open(target_path, 'wb') as f:
                while True:
                    chunk = await request.stream.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    bytes_written += len(chunk)
        except Exception as e:
            print(f"Stream write error: {e}")
            return {'error': f'Write failed: {e}'}, 500
                
        print(f"Upload complete: {target_path} ({bytes_written} bytes)")
        return {'status': 'ok', 'path': target_path, 'size': bytes_written}
    except Exception as e:
        print(f"General upload error: {e}")
        return {'error': f'Upload failed: {e}'}, 500


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


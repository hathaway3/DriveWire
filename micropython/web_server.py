try:
    from microdot_asyncio import Microdot, Response, Request, send_file
except ImportError:
    # Fallback for checking installation
    try:
        from microdot import Microdot, Response, Request, send_file
    except ImportError:
        # We can't log yet, but we can print for serial console
        print("Microdot not installed.")
        raise

import json
import os
import gc
import uasyncio as asyncio
from config import shared_config
import sd_card
import time_sync
import activity_led
import utime
import resilience

try:
    from typing import Optional, List, Dict, Any, Union
except ImportError:
    pass

app = Microdot()
# Microdot 1.3.4 uses Request class attributes for limits
Request.max_content_length = 100 * 1024 * 1024  # 100MB limit for uploads
Request.max_body_length = 16 * 1024          # Small body limit to force streaming
config = shared_config
_uploading = False  # Flag to prevent SD polling during uploads
_creating_disk = False
_disk_creation_progress = {'state': 'idle', 'written': 0, 'total': 0, 'filename': '', 'error': None}

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
        safe_config = dict(config.config)
        if safe_config.get('wifi_password'):
            safe_config['wifi_password'] = '********'
        return safe_config
    
    elif request.method == 'POST':
        try:
            new_config = request.json
            
            update_data = {}
            for key in ('baud_rate', 'wifi_ssid', 'wifi_password', 'ntp_server', 'timezone_offset', 'serial_map', 'syslog_server', 'syslog_port', 'wdt_enabled', 'log_level', 'remote_servers'):
                if key in new_config:
                    update_data[key] = new_config[key]
                    
            if 'drives' in new_config:
                drives = new_config['drives']
                if isinstance(drives, list) and len(drives) == 4:
                    update_data['drives'] = drives

            # SD card SPI pin config
            for sd_key in ('sd_spi_id', 'sd_sck', 'sd_mosi', 'sd_miso', 'sd_cs', 'sd_mount_point'):
                if sd_key in new_config:
                    update_data[sd_key] = new_config[sd_key]
            
            config.update(update_data)
            
            # Trigger reload on DriveWire Server if attached
            if hasattr(app, 'dw_server'):
                resilience.log("Reloading DriveWire Config...")
                await app.dw_server.reload_config()

            return {'status': 'ok'}
        except Exception as e:
            resilience.log(f"Failed to save config: {e}", level=3)
            return {"status": "error", "message": str(e)}, 500
        finally:
            gc.collect() # Clean up memory after parsing JSON payload

def _scan_dsk_dir(base_path: str, depth: int = 0, max_depth: int = 1) -> List[str]:
    """Recursively scan a directory for .dsk files up to max_depth levels deep."""
    results = []
    try:
        if base_path.startswith('/sd') and not sd_card.is_mounted():
            return []
        entries = os.listdir(base_path)
        if base_path.startswith('/sd'):
            activity_led.blink()
        for entry in entries:
            full_path = base_path.rstrip('/') + '/' + entry
            if entry.lower().endswith('.dsk'):
                results.append(full_path)
            elif depth < max_depth:
                # Check if it's a directory
                try:
                    s = os.stat(full_path)
                    if s[0] & 0x4000: # Directory bit
                        results.extend(_scan_dsk_dir(full_path, depth + 1, max_depth))
                except OSError:
                    pass
    except OSError:
        pass
    return results


_dsk_files_cache = None
_dsk_files_cache_ts = 0
_DSK_CACHE_TTL_MS = 10000  # 10 second TTL

def get_dsk_files():
    """Find all .dsk files on internal flash and SD card storage (cached 10s)."""
    global _dsk_files_cache, _dsk_files_cache_ts
    now = utime.ticks_ms()
    if _dsk_files_cache is not None and utime.ticks_diff(now, _dsk_files_cache_ts) < _DSK_CACHE_TTL_MS:
        return _dsk_files_cache
    
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
    _dsk_files_cache = unique
    _dsk_files_cache_ts = utime.ticks_ms()
    resilience.log_mem_info("DSK Cache Updated")
    return unique


def _sanitize_path(path):
    """Validate and normalize file paths. Returns sanitized path or None."""
    if not path or not isinstance(path, str):
        return None
    # Reject path traversal attempts (only block ".." as a full segment)
    if any(part == '..' for part in path.split('/')):
        return None
    # Must be under /sd/ or be a .dsk file directly in root
    if path.startswith('/sd/'):
        return path
    # Allow .dsk files from root level only (no subdirectory traversal)
    stripped = path.lstrip('/')
    if stripped.endswith('.dsk') and '/' not in stripped:
        return '/' + stripped
    return None


def _get_file_mtime(path):
    """Get a formatted modification timestamp for a file, or None."""
    try:
        st = os.stat(path)
        # MicroPython os.stat returns mtime at index 8 (seconds since epoch)
        mtime = st[8]
        # Convert epoch seconds to a readable string
        # MicroPython epoch is 2000-01-01, adjust for display
        import time
        t = time.localtime(mtime)
        return f"{t[0]:04d}-{t[1]:02d}-{t[2]:02d} {t[3]:02d}:{t[4]:02d}"
    except (OSError, OverflowError):
        return None


@app.route('/api/files')
async def files_endpoint(request):
    gc.collect()
    return get_dsk_files()


@app.route('/api/files/info')
async def files_info_endpoint(request):
    """Return metadata (size, modification time) for all .dsk files."""
    resilience.log_mem_info("Files Info Start")
    files = get_dsk_files()
    result = {}
    for f in files:
        try:
            st = os.stat(f)
            size = st[6]  # file size in bytes
            mtime_str = _get_file_mtime(f)
            result[f] = {'size': size, 'mtime': mtime_str}
        except OSError:
            result[f] = {'size': 0, 'mtime': None}
    gc.collect() # Clean up after massive dict creation
    return result


@app.route('/api/sd/status')
async def sd_status_endpoint(request):
    """Return SD card mount status and storage info."""
    gc.collect()
    if _uploading:
        # During uploads, return minimal info to avoid SPI access
        return {'mounted': True, 'mount_point': '/sd', 'busy': True}
    try:
        info = await sd_card.get_info()
        info['files_found'] = len([f for f in get_dsk_files() if f.startswith('/sd')])
        return info
    except ImportError:
        return {'mounted': False, 'mount_point': '/sd', 'error': 'sd_card module not available'}
    except Exception as e:
        return {'mounted': False, 'error': str(e)}

@app.route('/api/status')
async def status_endpoint(request):
    resilience.log_mem_info("Status Poll")
    try:
        # Always include server time (lightweight)
        try:
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
                    ds['is_remote'] = getattr(d, 'is_remote', False)
                    # Add file modification time for local files
                    if not ds['is_remote']:
                        ds['mtime'] = _get_file_mtime(d.filename)
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
    global _dsk_files_cache
    try:
        if not hasattr(app, 'dw_server'):
            return {'error': 'DriveWire Server not attached'}, 500
            
        body = request.json
        if not body or 'path' not in body:
            return {'error': 'Missing file path'}, 400
            
        path = body['path']
        
        # Security: sanitize path to prevent traversal attacks
        safe_path = _sanitize_path(path)
        if not safe_path:
            return {'error': 'Access denied: invalid file path'}, 403
        path = safe_path
        
        # Check if mounted
        for i, drive in enumerate(app.dw_server.drives):
            if drive and drive.filename == path:
                return {'error': f'Cannot delete: File is mounted in DRIVE {i}'}, 400
                
        # Attempt delete
        try:
            activity_led.blink()
            os.remove(path)
            _dsk_files_cache = None  # Invalidate cache
            return {'status': 'ok'}
        except OSError as e:
            return {'error': f'Delete failed: {e}'}, 500
            
    except Exception as e:
        return {'error': f'Delete error: {e}'}, 500
    finally:
        gc.collect() # Cleanup JSON parsing in serial config POST

@app.errorhandler(413)
async def request_too_large(request):
    print(f"413 Error: Request too large. Content-Length: {request.headers.get('Content-Length')}")
    return {'error': 'Request too large. Max size is 100MB.'}, 413

@app.route('/api/files/download', methods=['GET'])
async def download_file_endpoint(request):
    """Download a file if not currently mounted."""
    try:
        if not hasattr(app, 'dw_server'):
            return {'error': 'DriveWire Server not attached'}, 500
            
        path = request.args.get('path')
        if not path:
            return {'error': 'Missing file path query parameter'}, 400
            
        # Security: sanitize path to prevent traversal attacks
        safe_path = _sanitize_path(path)
        if not safe_path:
            return {'error': 'Access denied: invalid file path'}, 403
        path = safe_path
            
        # Check if mounted
        for i, drive in enumerate(app.dw_server.drives):
            if drive and drive.filename == path:
                return {'error': f'Cannot download: File is mounted in DRIVE {i}'}, 400
        
        # Verify file exists
        try:
            os.stat(path)
        except OSError:
            return {'error': 'File not found'}, 404
            
        resilience.log(f"Downloading file: {path}")
        # Send file as attachment
        filename = path.split('/')[-1]
        headers = {
            'Content-Disposition': f'attachment; filename="{filename}"',
            'Cache-Control': 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0'
        }
        activity_led.blink()
        res = send_file(path)
        res.headers.update(headers)
        return res
            
    except Exception as e:
        resilience.log(f"Download error: {e}", level=3)
        return {'error': f'Download error: {e}'}, 500
    finally:
        gc.collect()

@app.route('/api/files/create', methods=['POST'])
async def create_blank_dsk_endpoint(request):
    """Create a new blank zero-filled .dsk image file."""
    global _creating_disk, _disk_creation_progress
    try:
        if _creating_disk:
            return {'error': 'Disk creation already in progress'}, 409

        if not hasattr(app, 'dw_server'):
            return {'error': 'DriveWire Server not attached'}, 500
            
        body = request.json
        if not body or 'filename' not in body or 'size' not in body:
            return {'error': 'Missing filename or size parameter'}, 400
            
        filename = body['filename']
        try:
            size_bytes = int(body['size'])
        except ValueError:
            return {'error': 'Size must be an integer (bytes)'}, 400
            
        if size_bytes <= 0:
            return {'error': 'Size must be greater than zero'}, 400

        MAX_DSK_SIZE = 50 * 1024 * 1024  # 50MB - larger than any standard CoCo format
        if size_bytes > MAX_DSK_SIZE:
            return {'error': f'Size exceeds maximum ({MAX_DSK_SIZE // (1024*1024)}MB)'}, 400
            
        # Security: ensure it goes to /sd and ends with .dsk
        clean_name = filename.split('/')[-1].split('\\')[-1]
        if not clean_name.lower().endswith('.dsk'):
            clean_name += '.dsk'
        target_path = '/sd/' + clean_name
        
        # Check if file already exists
        try:
            os.stat(target_path)
            return {'error': f'File {clean_name} already exists. Please delete it first.'}, 400
        except OSError:
            pass # File doesn't exist, this is good
            
        # Check SD card space
        try:
            sd_stat = os.statvfs('/sd')
            sd_free = sd_stat[0] * sd_stat[3]
            if sd_free < size_bytes:
                return {'error': f'Insufficient SD card space. Need {size_bytes} bytes, have {sd_free} bytes.'}, 400
        except Exception as e:
            return {'error': f'SD card check failed: {e}'}, 500
            
        # Start the background task
        _creating_disk = True
        _disk_creation_progress = {
            'state': 'creating',
            'written': 0,
            'total': size_bytes,
            'filename': clean_name,
            'error': None
        }
        
        async def _do_create_blank_dsk():
            global _creating_disk, _disk_creation_progress, _dsk_files_cache
            try:
                activity_led.on() # Keep LED solid during heavy SD write operation
                chunk_size = 4096
                empty_chunk = bytearray(chunk_size)
                
                with open(target_path, 'wb') as f:
                    while _disk_creation_progress['written'] < size_bytes:
                        to_write = min(chunk_size, size_bytes - _disk_creation_progress['written'])
                        if to_write < chunk_size:
                            f.write(bytearray(to_write)) # Last partial chunk
                        else:
                            f.write(empty_chunk)
                        
                        _disk_creation_progress['written'] += to_write
                        
                        # Yield after EVERY chunk to maintain UART responsiveness
                        resilience.feed_wdt()
                        await asyncio.sleep(0)
                
                resilience.log(f"Successfully created blank disk: {target_path}")
                _disk_creation_progress['state'] = 'complete'
                _dsk_files_cache = None # Invalidate local file list cache
            except Exception as e:
                resilience.log(f"Blank disk creation failed: {e}", level=3)
                _disk_creation_progress['state'] = 'error'
                _disk_creation_progress['error'] = str(e)
                try:
                    os.remove(target_path)
                except OSError:
                    pass
            finally:
                _creating_disk = False
                activity_led.off()

        asyncio.create_task(_do_create_blank_dsk())
        return {'status': 'accepted', 'filename': clean_name, 'size': size_bytes}, 202
            
    except Exception as e:
        resilience.log(f"Disk creation request error: {e}", level=3)
        return {'error': f'Failed to process request: {e}'}, 500
    finally:
        gc.collect()

@app.route('/api/files/create/status', methods=['GET'])
async def create_disk_status_endpoint(request):
    """Return the status of an ongoing disk creation."""
    return _disk_creation_progress

@app.route('/api/files/upload', methods=['POST'])
async def upload_file_endpoint(request):
    """Handle file upload via streaming POST with X-Filename header."""
    global _uploading, _dsk_files_cache
    try:
        filename = request.headers.get('X-Filename')
        content_length = request.headers.get('Content-Length')
        resilience.log(f"Upload starting: {filename} (Content-Length: {content_length})")
        
        if not filename:
            resilience.log("Upload Error: Missing X-Filename header", level=2)
            return {'error': 'Missing X-Filename header.'}, 400
            
        if not filename.lower().endswith('.dsk'):
            resilience.log(f"Upload Error: Invalid file type: {filename}", level=2)
            return {'error': 'Only .dsk files are supported.'}, 400
            
        # Clean filename 
        clean_name = filename.split('/')[-1].split('\\')[-1]
        target_path = '/sd/' + clean_name
        total_size = int(content_length) if content_length else 0
        
        if total_size == 0:
            return {'error': 'Content-Length is required'}, 400
        
        # Quick SD card check
        try:
            sd_stat = os.statvfs('/sd')
            sd_free = sd_stat[0] * sd_stat[3]
            resilience.log(f"SD free: {sd_free // 1024}KB, need: {total_size // 1024}KB")
            if sd_free < total_size:
                return {'error': 'Insufficient SD card space'}, 400
        except Exception as e:
            resilience.log(f"SD check failed: {e}", level=3)
            return {'error': f'SD card not accessible: {e}'}, 500

        # Signal that an upload is in progress (prevents SD polling from interfering)
        _uploading = True
        app.upload_total = total_size
        app.upload_written = 0
        chunk_size = 4096  # Increased chunk size for better async batching
        bytes_written = 0
        
        # Async writing pipeline (without asyncio.Queue since it is missing in uasyncio)
        write_buffer = []
        data_ready = asyncio.Event()
        write_error = None
        
        async def sd_writer():
            nonlocal write_error
            try:
                with open(target_path, 'wb') as f:
                    while True:
                        await data_ready.wait()
                        
                        if write_buffer:
                            activity_led.on() # Solid LED while flushing network chunks to disk
                            
                        while write_buffer:
                            chunk = write_buffer.pop(0)
                            if chunk is None: # EOF signal
                                activity_led.off()
                                return
                            f.write(chunk)
                            app.upload_written += len(chunk)
                            # Yield after every chunk to let serial loop run
                            await asyncio.sleep(0)
                            
                        # Empty buffer, clear event and wait for more data
                        activity_led.off()
                        data_ready.clear()
            except Exception as e:
                write_error = e
                resilience.log(f"SD Background Writer Error: {e}", level=3)

        # Start the background writer task
        writer_task = asyncio.create_task(sd_writer())
        
        try:
            remaining = total_size
            while remaining > 0:
                if write_error:
                    raise Exception(f"Background write failed: {write_error}")
                    
                read_size = min(chunk_size, remaining)
                chunk = await request.stream.read(read_size)
                if not chunk:
                    resilience.log(f"Stream ended early at {bytes_written}/{total_size}", level=2)
                    break
                
                # Throttle network read if SD card is falling behind (Queue maxsize=3 alternative)
                while len(write_buffer) >= 3 and not write_error:
                    await asyncio.sleep(0.05)
                    
                # Push off to background writer
                write_buffer.append(chunk)
                data_ready.set()
                
                bytes_written += len(chunk)
                remaining -= len(chunk)
                
                # Manual memory optimization
                if bytes_written % (16 * chunk_size) == 0:
                    resilience.log(f"Received: {bytes_written}/{total_size} bytes")
                    resilience.feed_wdt()
                    gc.collect()
                    
            # After receiving all chunks, send EOF marker
            write_buffer.append(None)
            data_ready.set()
            
            # Wait for the background writer to finish emptying buffer
            while write_buffer and not write_error:
                await asyncio.sleep(0.05) 
            
            if write_error:
                raise Exception(f"Background write failed at EOF: {write_error}")
                
        except Exception as e:
            resilience.log(f"Upload pipeline error at {bytes_written}: {e}", level=3)
            _uploading = False
            
            # Cancel writer on error
            try:
                writer_task.cancel()
            except Exception:
                pass
            return {'error': f'Upload pipeline failed: {e}'}, 500
        finally:
            _uploading = False
                
        resilience.log(f"Upload complete: {target_path} ({bytes_written} bytes)")
        if bytes_written != total_size:
            resilience.log(f"Warning: size mismatch! Expected {total_size}, got {bytes_written}", level=2)
        
        return {'status': 'ok', 'path': target_path, 'size': bytes_written}
    except Exception as e:
        _uploading = False
        _dsk_files_cache = None  # Invalidate cache
        resilience.log(f"General upload error: {e}", level=3)
        return {'error': f'Upload failed: {e}'}, 500

@app.route('/api/files/upload_status', methods=['GET'])
async def upload_status_endpoint(request):
    """Return the exact number of bytes written to the SD card during an active upload."""
    if _uploading:
        return {'written': getattr(app, 'upload_written', 0), 'total': getattr(app, 'upload_total', 0)}
    else:
        return {'written': 0, 'total': 0}

@app.route('/api/serial/monitor', methods=['POST'])
async def monitor_chan_endpoint(request):
    if hasattr(app, 'dw_server'):
        try:
            body = request.json
            if not body:
                return {'error': 'Invalid JSON body'}, 400
            chan = body.get('chan', -1)
            chan = int(chan)
            if chan < -1 or chan >= 32:
                return {'error': 'Channel must be -1 (off) to 31'}, 400
            app.dw_server.monitor_channel = chan
            app.dw_server.terminal_buffer = bytearray() # Clear on change
            return {'status': 'ok'}
        except (ValueError, TypeError) as e:
            return {'error': f'Invalid channel: {e}'}, 400
    return {'error': 'DriveWire Server not attached'}, 500

# ---------------------------------------------------------------
# REMOTE DISK IMAGE ENDPOINTS
# ---------------------------------------------------------------

_cloning = False
_clone_progress = {'state': 'idle', 'progress': 0, 'total': 0, 'error': None}

def stream_remote_info(server_url):
    """Fetch info from a remote server and yield disk objects one by one.
    
    This avoids buffering the entire JSON response which can cause ENOMEM.
    """
    gc.collect()
    sock = resilience.open_remote_stream(server_url.rstrip('/') + '/info')
    if not sock:
        return
    
    try:
        import json
        buffer = bytearray()
        in_disks = False
        depth = 0
        
        while True:
            chunk = sock.recv(128)
            if not chunk:
                break
            resilience.feed_wdt()
            
            for b in chunk:
                c = chr(b)
                if not in_disks:
                    # Look for "disks": [
                    buffer.append(b)
                    if b == ord('['):
                        if b'"disks"' in buffer:
                            in_disks = True
                            buffer = bytearray()
                            depth = 1
                    elif len(buffer) > 100: 
                        buffer.pop(0) # Sliding window
                else:
                    # Inside the disks array
                    if b == ord(',' ) and depth == 1:
                        # Skip commas between objects in the array
                        continue
                    buffer.append(b)
                    if b == ord('{'):
                        depth += 1
                    elif b == ord('}'):
                        depth -= 1
                        if depth == 1:
                            # Found a complete disk object
                            try:
                                yield json.loads(buffer)
                            except:
                                pass
                            buffer = bytearray()
                    elif b == ord(']'):
                        depth -= 1
                        if depth == 0:
                            in_disks = False
                            break
    except Exception as e:
        resilience.log(f"Remote info stream error ({server_url}): {e}", level=2)
    finally:
        try:
            sock.close()
        except Exception:
            pass
        gc.collect()

def stream_remote_files(server_url):
    """Fetch list of .dsk files from a remote server using raw sockets.
    
    Yields one filename at a time, never holding more than ~100 bytes.
    """
    gc.collect()
    sock = resilience.open_remote_stream(server_url.rstrip('/') + '/files')
    if not sock:
        return
    
    try:
        in_string = False
        escape = False
        current_str = []
        
        while True:
            chunk = sock.recv(64)
            if not chunk:
                break
            resilience.feed_wdt()
            for b in chunk:
                c = chr(b) if isinstance(b, int) else chr(b)
                if escape:
                    if c == 'n': current_str.append('\n')
                    elif c == 'r': current_str.append('\r')
                    elif c == 't': current_str.append('\t')
                    else: current_str.append(c)
                    escape = False
                elif c == '\\':
                    escape = True
                elif c == '"':
                    if in_string:
                        yield ''.join(current_str)
                        current_str = []
                        in_string = False
                    else:
                        in_string = True
                elif in_string:
                    current_str.append(c)
    except Exception as e:
        resilience.log(f"Remote files stream error ({server_url}): {e}", level=2)
    finally:
        try:
            sock.close()
        except Exception:
            pass
        gc.collect()

@app.route('/api/remote/files')
async def remote_files_endpoint(request):
    """List .dsk files from all configured remote servers (streaming JSON)."""
    gc.collect()
    
    async def generate():
        yield '{"servers":['
        remote_servers = config.get('remote_servers') or []
        first_server = True
        for srv in remote_servers:
            if not first_server:
                yield ','
            first_server = False
            
            url = srv.get('url', '')
            name = srv.get('name', url)
            if not url:
                yield json.dumps({"name": name, "url": url, "files": []})
                continue
                
            yield '{"name":' + json.dumps(name) + ',"url":' + json.dumps(url) + ',"files":['
            
            first_file = True
            for filename in stream_remote_files(url):
                if not first_file:
                    yield ','
                yield json.dumps(filename)
                first_file = False
                resilience.feed_wdt()
            
            yield ']}'
            gc.collect()
            
        yield ']}'

    return Response(generate(), headers={'Content-Type': 'application/json'})

@app.route('/api/remote/test', methods=['POST'])
async def remote_test_endpoint(request):
    """Test connectivity to a remote sector server (streaming proxy)."""
    try:
        body = request.json
        url = body.get('url', '').rstrip('/')
        if not url:
            return {'error': 'Missing URL'}, 400
        
        # Connectivity check
        sock = resilience.open_remote_stream(url + '/info')
        if not sock:
            return {'status': 'error', 'message': 'Cannot reach remote server'}, 502
        sock.close()

        async def generate():
            yield '{"status":"ok","info":'
            rsock = resilience.open_remote_stream(url + '/info')
            if rsock:
                try:
                    while True:
                        chunk = rsock.recv(512)
                        if not chunk: break
                        yield chunk
                        resilience.feed_wdt()
                finally:
                    rsock.close()
            yield '}'

        return Response(generate(), headers={'Content-Type': 'application/json'})
    except Exception as e:
        return {'status': 'error', 'message': str(e)}, 502
    finally:
        gc.collect()

@app.route('/api/remote/clone', methods=['POST'])
async def remote_clone_endpoint(request):
    """Clone a remote disk image to local storage and hot-swap."""
    global _cloning, _clone_progress
    try:
        if _cloning:
            return {'error': 'Clone already in progress'}, 409

        if not hasattr(app, 'dw_server'):
            return {'error': 'DriveWire Server not attached'}, 500

        body = request.json
        remote_url = body.get('remote_url', '').rstrip('/')
        disk_name = body.get('disk_name', '')
        local_path = body.get('local_path', '')
        drive_num = body.get('drive_num', -1)

        if not remote_url or not disk_name:
            return {'error': 'Missing remote_url or disk_name'}, 400

        # Auto-generate local path if not specified
        if not local_path:
            local_path = '/sd/' + disk_name

        # Check SD card space
        try:
            # Find the disk using streaming parser to avoid buffering massive /info
            total_sectors = 0
            for d in stream_remote_info(remote_url):
                if d['name'] == disk_name:
                    total_sectors = d.get('total_sectors', 0)
                    break
            
            if total_sectors == 0:
                return {'error': f'Disk {disk_name} not found on remote server'}, 404

            total_bytes = total_sectors * 256
            try:
                sd_stat = os.statvfs('/sd')
                sd_free = sd_stat[0] * sd_stat[3]
                if sd_free < total_bytes:
                    return {'error': f'Insufficient SD space: need {total_bytes}, have {sd_free}'}, 400
            except (OSError, AttributeError):
                pass  # May not be on SD card path

        except Exception as e:
            return {'error': f'Remote server query failed: {e}'}, 502

        # Start clone in background
        _cloning = True
        _clone_progress = {'state': 'downloading', 'progress': 0, 'total': total_sectors, 'error': None}

        async def _do_clone():
            global _cloning, _clone_progress, _dsk_files_cache
            try:
                activity_led.on()
                
                # Resolve remote host IP once to avoid repeated getaddrinfo calls
                import usocket
                host_url = remote_url.split('://', 1)[1] if '://' in remote_url else remote_url
                host = host_url.split('/')[0]
                port = 80
                if ':' in host:
                    host, port_str = host.rsplit(':', 1)
                    port = int(port_str)
                
                resilience.log(f"Resolving {host}:{port} for clone...")
                remote_addr = usocket.getaddrinfo(host, port)[0][-1]
                resilience.log_mem_info("Clone Start (Single Stream)")

                # Request ALL sectors in a single persistent stream
                url = f"{remote_url}/sectors/{disk_name}/0?count={total_sectors}"
                sock = resilience.open_remote_stream(url, addr=remote_addr)
                if not sock:
                    raise Exception(f"Failed to open clone stream at {url}")

                try:
                    CHUNK_SIZE = 4096 # 16 sectors at a time (SD-aligned)
                    buffer = bytearray(CHUNK_SIZE)
                    view = memoryview(buffer)
                    
                    with open(local_path, 'wb') as f:
                        lsn = 0
                        while lsn < total_sectors:
                            count = min(CHUNK_SIZE // 256, total_sectors - lsn)
                            expected_bytes = count * 256
                            
                            # Read from persistent socket
                            pos = 0
                            while pos < expected_bytes:
                                n = sock.readinto(view[pos:expected_bytes])
                                if n == 0: break
                                pos += n
                                resilience.feed_wdt()
                            
                            if pos < expected_bytes:
                                raise Exception(f"Stream ended early at LSN {lsn} (got {pos}/{expected_bytes})")
                            
                            f.write(view[:expected_bytes])
                            lsn += count
                            _clone_progress['progress'] = lsn
                            
                            # Yield to web server and other tasks
                            await asyncio.sleep(0)
                            
                            if lsn % 128 == 0:
                                resilience.log_mem_info(f"Cloning {lsn}/{total_sectors}")
                                gc.collect()
                finally:
                    sock.close()
                    gc.collect()

                activity_led.off()
                _clone_progress['state'] = 'swapping'

                # Hot-swap if drive_num specified
                if 0 <= drive_num < 4:
                    from drivewire import VirtualDrive
                    new_drive = VirtualDrive(local_path)
                    if new_drive.file:
                        await app.dw_server.swap_drive(drive_num, new_drive)
                        # Update config to point to local path and persist
                        drives = config.get('drives')
                        drives[drive_num] = local_path
                        config.set('drives', drives)
                        config.save()
                        _clone_progress['state'] = 'complete'
                    else:
                        _clone_progress['state'] = 'error'
                        _clone_progress['error'] = 'Failed to open cloned file'
                else:
                    _clone_progress['state'] = 'complete'

                resilience.log(f"Clone complete: {disk_name} -> {local_path}")
                _dsk_files_cache = None  # Invalidate cache
            except Exception as e:
                resilience.log(f"Clone error: {e}", level=3)
                _clone_progress['state'] = 'error'
                _clone_progress['error'] = str(e)
                activity_led.off()
                # Cleanup partial file
                try:
                    os.remove(local_path)
                except OSError:
                    pass
            finally:
                _cloning = False
                gc.collect()

        asyncio.create_task(_do_clone())
        return {'status': 'started', 'total_sectors': total_sectors}

    except Exception as e:
        _cloning = False
        return {'error': f'Clone request failed: {e}'}, 500
    finally:
        gc.collect()

@app.route('/api/remote/clone/status')
async def remote_clone_status_endpoint(request):
    """Return clone operation progress."""
    return _clone_progress

def start():
    resilience.log("Starting Web Server...")
    app.run(port=80, debug=True)


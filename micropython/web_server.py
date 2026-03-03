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
import gc
import uasyncio as asyncio
import sd_card
import time_sync
import activity_led

app = Microdot()
# Microdot 1.3.4 uses Request class attributes for limits
Request.max_content_length = 100 * 1024 * 1024  # 100MB limit for uploads
Request.max_body_length = 16 * 1024          # Small body limit to force streaming
config = shared_config
_uploading = False  # Flag to prevent SD polling during uploads

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
            
            update_data = {}
            for key in ('baud_rate', 'wifi_ssid', 'wifi_password', 'ntp_server', 'timezone_offset', 'serial_map', 'syslog_server', 'syslog_port', 'remote_servers'):
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
                print("Reloading DriveWire Config...")
                app.dw_server.reload_config()

            return {'status': 'ok'}
        except Exception as e:
            print(f"Failed to save config: {e}")
            syslog.logger.log(f"Failed to save config: {e}", severity=3)
            return {"status": "error", "message": str(e)}, 500
        finally:
            gc.collect() # Clean up memory after parsing JSON payload

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
            
        # Security: only allow downloading from /sd or non-system files
        if not path.startswith('/sd/') and not path.endswith('.dsk'):
            return {'error': 'Access denied: Cannot download system files'}, 403
            
        # Check if mounted
        for i, drive in enumerate(app.dw_server.drives):
            if drive and drive.filename == path:
                return {'error': f'Cannot download: File is mounted in DRIVE {i}'}, 400
        
        # Verify file exists
        try:
            os.stat(path)
        except OSError:
            return {'error': 'File not found'}, 404
            
        print(f"Downloading file: {path}")
        # Send file as attachment
        filename = path.split('/')[-1]
        headers = {
            'Content-Disposition': f'attachment; filename="{filename}"',
            'Cache-Control': 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0'
        }
        res = send_file(path)
        res.headers.update(headers)
        return res
            
    except Exception as e:
        print(f"Download error: {e}")
        return {'error': f'Download error: {e}'}, 500
    finally:
        gc.collect()

@app.route('/api/files/create', methods=['POST'])
async def create_blank_dsk_endpoint(request):
    """Create a new blank zero-filled .dsk image file."""
    try:
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
            
        # Generate the file with zero-fill chunks to prevent memory exhaustion
        print(f"Creating blank disk image: {target_path} ({size_bytes} bytes)")
        
        try:
            chunk_size = 4096
            written = 0
            empty_chunk = bytearray(chunk_size)
            
            try:
                activity_led.on() # Keep LED solid during heavy SD write operation
                with open(target_path, 'wb') as f:
                    while written < size_bytes:
                        to_write = min(chunk_size, size_bytes - written)
                        if to_write < chunk_size:
                            f.write(bytearray(to_write)) # Last partial chunk
                        else:
                            f.write(empty_chunk)
                        written += to_write
                        
                        if written % (16 * chunk_size) == 0:
                            await asyncio.sleep(0) # yield periodically for massive files
            finally:
                activity_led.off()
                        
            print(f"Successfully created: {target_path}")
            return {'status': 'ok', 'filename': clean_name, 'size': size_bytes}, 201
            
        except Exception as e:
            try:
                os.remove(target_path) # cleanup partial broken file
            except:
                pass
            return {'error': f'File creation failed: {e}'}, 500
            
    except Exception as e:
        print(f"Disk creation request error: {e}")
        return {'error': f'Failed to process request: {e}'}, 500
    finally:
        gc.collect()

@app.route('/api/files/upload', methods=['POST'])
async def upload_file_endpoint(request):
    """Handle file upload via streaming POST with X-Filename header."""
    global _uploading
    try:
        filename = request.headers.get('X-Filename')
        content_length = request.headers.get('Content-Length')
        print(f"Upload starting: {filename} (Content-Length: {content_length})")
        
        if not filename:
            print("Upload Error: Missing X-Filename header")
            return {'error': 'Missing X-Filename header.'}, 400
            
        if not filename.lower().endswith('.dsk'):
            print(f"Upload Error: Invalid file type: {filename}")
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
            print(f"SD free: {sd_free // 1024}KB, need: {total_size // 1024}KB")
            if sd_free < total_size:
                return {'error': 'Insufficient SD card space'}, 400
        except Exception as e:
            print(f"SD check failed: {e}")
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
                            
                        # Empty buffer, clear event and wait for more data
                        activity_led.off()
                        data_ready.clear()
            except Exception as e:
                write_error = e
                print(f"SD Background Writer Error: {e}")

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
                    print(f"Stream ended early at {bytes_written}/{total_size}")
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
                    print(f"Received: {bytes_written}/{total_size} bytes")
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
            print(f"Upload pipeline error at {bytes_written}: {e}")
            _uploading = False
            
            # Cancel writer on error
            try:
                writer_task.cancel()
            except:
                pass
            return {'error': f'Upload pipeline failed: {e}'}, 500
        finally:
            _uploading = False
                
        print(f"Upload complete: {target_path} ({bytes_written} bytes)")
        if bytes_written != total_size:
            print(f"Warning: size mismatch! Expected {total_size}, got {bytes_written}")
        
        return {'status': 'ok', 'path': target_path, 'size': bytes_written}
    except Exception as e:
        _uploading = False
        print(f"General upload error: {e}")
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
            app.dw_server.monitor_channel = int(chan)
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

def _fetch_remote_files(server_url):
    """Fetch list of .dsk files from a remote sector server."""
    try:
        import urequests
        resp = urequests.get(server_url.rstrip('/') + '/files')
        if resp.status_code == 200:
            files = resp.json()
            resp.close()
            return files
        resp.close()
    except Exception as e:
        print(f"Remote files fetch error ({server_url}): {e}")
    return []

@app.route('/api/remote/files')
async def remote_files_endpoint(request):
    """List .dsk files from all configured remote servers."""
    remote_servers = config.get('remote_servers') or []
    result = []
    for srv in remote_servers:
        url = srv.get('url', '')
        name = srv.get('name', url)
        if not url:
            continue
        files = _fetch_remote_files(url)
        for f in files:
            result.append({
                'name': f,
                'server': name,
                'url': url,
                'path': url.rstrip('/') + '/disk/' + f
            })
    return result

@app.route('/api/remote/test', methods=['POST'])
async def remote_test_endpoint(request):
    """Test connectivity to a remote sector server."""
    try:
        body = request.json
        url = body.get('url', '').rstrip('/')
        if not url:
            return {'error': 'Missing URL'}, 400
        import urequests
        resp = urequests.get(url + '/info')
        if resp.status_code == 200:
            info = resp.json()
            resp.close()
            return {'status': 'ok', 'info': info}
        resp.close()
        return {'status': 'error', 'message': f'HTTP {resp.status_code}'}, 502
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
            import urequests
            resp = urequests.get(remote_url + '/info')
            if resp.status_code != 200:
                resp.close()
                return {'error': 'Cannot reach remote server'}, 502
            info = resp.json()
            resp.close()

            # Find the disk in info
            total_sectors = 0
            for d in info.get('disks', []):
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
            except:
                pass  # May not be on SD

        except Exception as e:
            return {'error': f'Remote server query failed: {e}'}, 502

        # Start clone in background
        _cloning = True
        _clone_progress = {'state': 'downloading', 'progress': 0, 'total': total_sectors, 'error': None}

        async def _do_clone():
            global _cloning, _clone_progress
            try:
                import urequests
                BULK_COUNT = 16  # 16 sectors = 4KB per request (SD-aligned)
                activity_led.on()

                with open(local_path, 'wb') as f:
                    lsn = 0
                    while lsn < total_sectors:
                        count = min(BULK_COUNT, total_sectors - lsn)
                        resp = urequests.get(f"{remote_url}/sectors/{disk_name}/{lsn}?count={count}")
                        if resp.status_code == 200:
                            f.write(resp.content)
                            resp.close()
                        else:
                            resp.close()
                            raise Exception(f"HTTP {resp.status_code} at LSN {lsn}")
                        lsn += count
                        _clone_progress['progress'] = lsn
                        await asyncio.sleep(0)  # Yield to other tasks
                        if lsn % 128 == 0:
                            gc.collect()

                activity_led.off()
                _clone_progress['state'] = 'swapping'

                # Hot-swap if drive_num specified
                if 0 <= drive_num < 4:
                    from drivewire import VirtualDrive
                    new_drive = VirtualDrive(local_path)
                    if new_drive.file:
                        app.dw_server.swap_drive(drive_num, new_drive)
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

                print(f"Clone complete: {disk_name} -> {local_path}")
            except Exception as e:
                print(f"Clone error: {e}")
                _clone_progress['state'] = 'error'
                _clone_progress['error'] = str(e)
                activity_led.off()
                # Cleanup partial file
                try:
                    os.remove(local_path)
                except:
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
    print("Starting Web Server...")
    app.run(port=80, debug=True)


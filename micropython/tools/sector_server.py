#!/usr/bin/env python3
"""
DriveWire Remote Sector Server

A lightweight HTTP server that serves disk image sectors over the network.
Run this on a Linux/Mac/Windows machine to share .dsk images with a
DriveWire Pico W server.

Usage:
    python sector_server.py --dir /path/to/disk/images --port 8080

Endpoints:
    GET  /info                          - Server info and available disks
    GET  /files                         - List all .dsk files
    GET  /sector/<filename>/<lsn>       - Read a single 256-byte sector
    GET  /sectors/<filename>/<lsn>?count=N  - Read N consecutive sectors (bulk)
    PUT  /sector/<filename>/<lsn>       - Write a single 256-byte sector
"""

import argparse
import json
import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

SECTOR_SIZE = 256
DEFAULT_PORT = 8080


class SectorHandler(BaseHTTPRequestHandler):
    """HTTP request handler for sector-level disk image access."""

    def log_message(self, format, *args):
        """Override to add cleaner logging."""
        print(f"[{self.log_date_time_string()}] {format % args}")

    def _send_json(self, data, status=200):
        body = json.dumps(data).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def _send_binary(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/octet-stream')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(data)

    def _send_error(self, status, message):
        self._send_json({'error': message}, status)

    def _get_disk_path(self, filename):
        """Resolve and validate a disk image filename."""
        # Security: prevent path traversal
        safe_name = os.path.basename(filename)
        path = os.path.join(self.server.disk_dir, safe_name)
        if not os.path.isfile(path):
            return None
        return path

    def _list_disks(self):
        """List all .dsk files in the serving directory."""
        disks = []
        try:
            for entry in os.listdir(self.server.disk_dir):
                if entry.lower().endswith('.dsk'):
                    full_path = os.path.join(self.server.disk_dir, entry)
                    size = os.path.getsize(full_path)
                    disks.append({
                        'name': entry,
                        'size': size,
                        'total_sectors': size // SECTOR_SIZE
                    })
        except OSError as e:
            print(f"Error listing directory: {e}")
        disks.sort(key=lambda d: d['name'])
        return disks

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip('/')
        query = parse_qs(parsed.query)

        # GET /info - Server info
        if path == '/info':
            disks = self._list_disks()
            self._send_json({
                'name': self.server.server_name,
                'version': '1.0',
                'disk_count': len(disks),
                'disks': disks
            })
            return

        # GET /files - List .dsk files
        if path == '/files':
            disks = self._list_disks()
            self._send_json([d['name'] for d in disks])
            return

        # GET /sector/<filename>/<lsn> - Read single sector
        parts = path.split('/')
        if len(parts) == 4 and parts[1] == 'sector':
            filename = parts[2]
            try:
                lsn = int(parts[3])
            except ValueError:
                self._send_error(400, 'Invalid LSN')
                return

            disk_path = self._get_disk_path(filename)
            if not disk_path:
                self._send_error(404, f'Disk image not found: {filename}')
                return

            try:
                with open(disk_path, 'rb') as f:
                    f.seek(lsn * SECTOR_SIZE)
                    data = f.read(SECTOR_SIZE)
                    if len(data) < SECTOR_SIZE:
                        data = data + bytes(SECTOR_SIZE - len(data))
                    self._send_binary(data)
            except Exception as e:
                self._send_error(500, f'Read error: {e}')
            return

        # GET /sectors/<filename>/<lsn>?count=N - Bulk read
        if len(parts) == 4 and parts[1] == 'sectors':
            filename = parts[2]
            try:
                start_lsn = int(parts[3])
            except ValueError:
                self._send_error(400, 'Invalid LSN')
                return

            count = int(query.get('count', [1])[0])
            if count < 1 or count > 64:  # Safety limit
                self._send_error(400, 'Count must be 1-64')
                return

            disk_path = self._get_disk_path(filename)
            if not disk_path:
                self._send_error(404, f'Disk image not found: {filename}')
                return

            try:
                with open(disk_path, 'rb') as f:
                    f.seek(start_lsn * SECTOR_SIZE)
                    data = f.read(count * SECTOR_SIZE)
                    # Pad if we hit end of file
                    expected = count * SECTOR_SIZE
                    if len(data) < expected:
                        data = data + bytes(expected - len(data))
                    self._send_binary(data)
            except Exception as e:
                self._send_error(500, f'Bulk read error: {e}')
            return

        self._send_error(404, 'Not found')

    def do_PUT(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip('/')
        parts = path.split('/')

        # PUT /sector/<filename>/<lsn> - Write single sector
        if len(parts) == 4 and parts[1] == 'sector':
            filename = parts[2]
            try:
                lsn = int(parts[3])
            except ValueError:
                self._send_error(400, 'Invalid LSN')
                return

            disk_path = self._get_disk_path(filename)
            if not disk_path:
                self._send_error(404, f'Disk image not found: {filename}')
                return

            content_length = int(self.headers.get('Content-Length', 0))
            if content_length != SECTOR_SIZE:
                self._send_error(400, f'Data must be exactly {SECTOR_SIZE} bytes')
                return

            data = self.rfile.read(SECTOR_SIZE)
            try:
                with open(disk_path, 'r+b') as f:
                    f.seek(lsn * SECTOR_SIZE)
                    f.write(data)
                    f.flush()
                self._send_json({'status': 'ok'})
            except Exception as e:
                self._send_error(500, f'Write error: {e}')
            return

        self._send_error(404, 'Not found')

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, PUT, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()


def main():
    parser = argparse.ArgumentParser(
        description='DriveWire Remote Sector Server',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    %(prog)s --dir /home/user/disks
    %(prog)s --dir ./images --port 9090 --name "Build Server"
        """
    )
    parser.add_argument('--dir', default='.', help='Directory containing .dsk files (default: current directory)')
    parser.add_argument('--port', type=int, default=DEFAULT_PORT, help=f'Port to listen on (default: {DEFAULT_PORT})')
    parser.add_argument('--name', default='DriveWire Sector Server', help='Server name shown in /info')
    parser.add_argument('--bind', default='0.0.0.0', help='Address to bind to (default: 0.0.0.0)')

    args = parser.parse_args()

    # Resolve and validate directory
    disk_dir = os.path.abspath(args.dir)
    if not os.path.isdir(disk_dir):
        print(f"Error: Directory not found: {disk_dir}")
        sys.exit(1)

    # Count available disk images
    dsk_files = [f for f in os.listdir(disk_dir) if f.lower().endswith('.dsk')]

    print(f"╔═══════════════════════════════════════════════╗")
    print(f"║  DriveWire Remote Sector Server v1.0          ║")
    print(f"╠═══════════════════════════════════════════════╣")
    print(f"║  Directory: {disk_dir:<34}║")
    print(f"║  Disks:     {len(dsk_files):<34}║")
    print(f"║  Bind:      {args.bind}:{args.port:<26}║")
    print(f"║  Name:      {args.name:<34}║")
    print(f"╚═══════════════════════════════════════════════╝")
    print()

    if not dsk_files:
        print("Warning: No .dsk files found in the specified directory.")
    else:
        for f in sorted(dsk_files):
            size = os.path.getsize(os.path.join(disk_dir, f))
            print(f"  📀 {f} ({size:,} bytes, {size // SECTOR_SIZE} sectors)")
        print()

    server = HTTPServer((args.bind, args.port), SectorHandler)
    server.disk_dir = disk_dir
    server.server_name = args.name

    print(f"Listening on {args.bind}:{args.port} ... (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_shutdown()


if __name__ == '__main__':
    main()

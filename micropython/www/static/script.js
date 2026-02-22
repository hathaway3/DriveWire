document.addEventListener('DOMContentLoaded', init);

/** Escape HTML special characters to prevent XSS */
function escHtml(str) {
    if (str == null) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

/** Safe parseInt with fallback for empty/invalid inputs */
function safeInt(val, fallback) {
    const n = parseInt(val, 10);
    return isNaN(n) ? fallback : n;
}

async function fetchConfig() {
    try {
        const response = await fetch('/api/config');
        if (!response.ok) {
            console.error("Config API returned", response.status);
            return {};
        }
        return await response.json();
    } catch (e) {
        console.error("Failed to fetch config", e);
        return {};
    }
}

async function fetchFiles() {
    try {
        const response = await fetch('/api/files?t=' + Date.now());
        if (!response.ok) {
            console.error("Files API returned", response.status);
            return [];
        }
        return await response.json();
    } catch (e) {
        console.error("Failed to fetch files", e);
        return [];
    }
}

async function init() {
    const [config, files] = await Promise.all([fetchConfig(), fetchFiles()]);

    document.getElementById('baud').value = config.baud_rate || 115200;
    document.getElementById('ssid').value = config.wifi_ssid || '';
    document.getElementById('wifi_pass').value = config.wifi_password || '';
    document.getElementById('ntp_server').value = config.ntp_server || 'pool.ntp.org';
    document.getElementById('tz_offset').value = config.timezone_offset || 0;

    // SD card SPI pin config
    document.getElementById('sd_spi_id').value = config.sd_spi_id != null ? config.sd_spi_id : 1;
    document.getElementById('sd_sck').value = config.sd_sck != null ? config.sd_sck : 10;
    document.getElementById('sd_mosi').value = config.sd_mosi != null ? config.sd_mosi : 11;
    document.getElementById('sd_miso').value = config.sd_miso != null ? config.sd_miso : 12;
    document.getElementById('sd_cs').value = config.sd_cs != null ? config.sd_cs : 13;
    document.getElementById('sd_mount_point').value = config.sd_mount_point || '/sd';

    const container = document.getElementById('drives-container');
    container.innerHTML = '';
    const currentDrives = config.drives || [null, null, null, null];
    const safeFiles = Array.isArray(files) ? files : [];

    // Build options with filename display and storage badge (XSS-safe)
    let baseOptions = '<option value="">(NO DISK)</option>';
    safeFiles.forEach(f => {
        const fname = String(f).split('/').pop();
        const badge = String(f).startsWith('/sd') ? '\uD83D\uDCBE' : '\uD83D\uDCC1';
        baseOptions += `<option value="${escHtml(f)}">${badge} ${escHtml(fname)}</option>`;
    });

    for (let i = 0; i < 4; i++) {
        const div = document.createElement('div');
        const currentVal = currentDrives[i] || '';

        // Ensure current value is in the list
        let options = baseOptions;
        if (currentVal && !safeFiles.includes(currentVal)) {
            const missingName = String(currentVal).split('/').pop();
            options += `<option value="${escHtml(currentVal)}">\u26A0 ${escHtml(missingName)} (MISSING)</option>`;
        }

        div.innerHTML = `
            <label>DRIVE ${i}:</label>
            <select id="drive_${i}">
                ${options}
            </select>
        `;
        container.appendChild(div);

        // Set selected value
        document.getElementById(`drive_${i}`).value = currentVal;
    }

    renderSerialMap(config.serial_map || {});

    // Check SD card status on load
    pollSdStatus();

    // Initialize File Manager listeners
    initFilesTab();

    // Start Polling
    setInterval(pollStatus, 1000);  // 1 second for live time + heartbeat
    setInterval(pollSdStatus, 10000);  // SD status every 10s
}

const VALID_TABS = ['config', 'status', 'terminal', 'drives', 'files'];
let mountedFiles = [];
let isUploading = false;
let _dialogOpen = false;

function switchTab(tabName) {
    if (!VALID_TABS.includes(tabName)) return;

    // Hide all tabs
    document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));

    // Show selected
    const tabEl = document.getElementById(`tab-${tabName}`);
    if (tabEl) tabEl.classList.add('active');

    // Button style
    const btns = document.querySelectorAll('.tab-btn');
    const tabIdx = VALID_TABS.indexOf(tabName);
    if (tabIdx >= 0 && btns[tabIdx]) btns[tabIdx].classList.add('active');

    if (tabName === 'files') {
        refreshFilesTab();
    }
    if (tabName === 'drives') {
        refreshDriveSelects();
    }
}

async function refreshDriveSelects() {
    const files = await fetchFiles();
    const safeFiles = Array.isArray(files) ? files : [];

    // Build fresh options
    let baseOptions = '<option value="">(NO DISK)</option>';
    safeFiles.forEach(f => {
        const fname = String(f).split('/').pop();
        const badge = String(f).startsWith('/sd') ? '\uD83D\uDCBE' : '\uD83D\uDCC1';
        baseOptions += `<option value="${escHtml(f)}">${badge} ${escHtml(fname)}</option>`;
    });

    for (let i = 0; i < 4; i++) {
        const sel = document.getElementById(`drive_${i}`);
        if (!sel) continue;
        const currentVal = sel.value;

        let options = baseOptions;
        if (currentVal && !safeFiles.includes(currentVal)) {
            const missingName = String(currentVal).split('/').pop();
            options += `<option value="${escHtml(currentVal)}">\u26A0 ${escHtml(missingName)} (MISSING)</option>`;
        }

        sel.innerHTML = options;
        sel.value = currentVal;
    }
}

async function refreshFilesTab() {
    const listBody = document.getElementById('files-list');
    listBody.innerHTML = '<tr><td colspan="2">LOADING FILES...</td></tr>';

    const files = await fetchFiles();
    listBody.innerHTML = '';

    if (!files || files.length === 0) {
        listBody.innerHTML = '<tr><td colspan="2">NO DISK IMAGES FOUND.</td></tr>';
        return;
    }

    // Only show files on SD or root that are .dsk
    files.forEach(f => {
        const tr = document.createElement('tr');
        const fname = f.split('/').pop();
        const isMounted = mountedFiles.includes(f);

        const deleteBtn = document.createElement('button');
        deleteBtn.className = isMounted ? 'btn btn-sm btn-disabled' : 'btn btn-sm btn-danger';
        deleteBtn.textContent = 'DELETE';
        if (isMounted) {
            deleteBtn.title = 'Disk image mounted and in use';
            deleteBtn.onclick = null;
        } else {
            deleteBtn.onclick = () => deleteFile(f);
        }

        tr.innerHTML = `
            <td><span class="file-icon">${f.startsWith('/sd') ? '\uD83D\uDCBE' : '\uD83D\uDCC1'}</span> ${escHtml(fname)}</td>
            <td></td>
        `;
        tr.cells[1].appendChild(deleteBtn);
        listBody.appendChild(tr);
    });
}

async function customConfirm(message) {
    return new Promise(resolve => {
        const overlay = document.getElementById('custom-confirm');
        const msgEl = document.getElementById('confirm-msg');
        const btnYes = document.getElementById('confirm-yes');
        const btnNo = document.getElementById('confirm-no');

        msgEl.innerText = message;
        overlay.style.display = 'flex';
        _dialogOpen = true; // Still keeps background polling tidy

        const cleanup = () => {
            overlay.style.display = 'none';
            _dialogOpen = false;
            btnYes.onclick = null;
            btnNo.onclick = null;
        };

        btnYes.onclick = () => { cleanup(); resolve(true); };
        btnNo.onclick = () => { cleanup(); resolve(false); };
    });
}

async function deleteFile(path) {
    const confirmed = await customConfirm(`ARE YOU SURE YOU WANT TO DELETE\n${path}?`);
    if (!confirmed) return;

    try {
        const response = await fetch('/api/files/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: path })
        });
        const result = await response.json();
        if (result.status === 'ok') {
            refreshFilesTab();
            refreshDriveSelects();
        } else {
            alert('DELETE FAILED: ' + result.error);
        }
    } catch (e) {
        alert('DELETE FAILED: ' + e);
    }
}

function initFilesTab() {
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');

    dropZone.onclick = () => fileInput.click();

    dropZone.ondragover = (e) => {
        e.preventDefault();
        dropZone.classList.add('dragover');
    };

    dropZone.ondragleave = () => dropZone.classList.remove('dragover');

    dropZone.ondrop = (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        handleFileUpload(e.dataTransfer.files);
    };

    fileInput.onchange = () => handleFileUpload(fileInput.files);
}

async function handleFileUpload(files) {
    if (!files || files.length === 0) return;
    console.log("Upload started: pausing background polling");
    isUploading = true;

    const progressContainer = document.getElementById('progress-container');
    const progressBar = document.getElementById('progress-bar');
    const statusEl = document.getElementById('upload-status');

    progressContainer.style.display = 'block';
    statusEl.innerText = 'UPLOADING...';
    statusEl.className = 'status'; // Reset classes
    statusEl.style.display = 'block';

    for (let i = 0; i < files.length; i++) {
        const file = files[i];
        if (!file.name.toLowerCase().endsWith('.dsk')) {
            statusEl.innerText = `SKIPPING ${file.name}: ONLY .DSK ALLOWED`;
            statusEl.classList.add('error');
            continue;
        }

        try {
            const xhr = new XMLHttpRequest();
            const promise = new Promise((resolve, reject) => {
                xhr.upload.onprogress = (e) => {
                    if (e.lengthComputable) {
                        const pct = (e.loaded / e.total) * 100;
                        progressBar.style.width = pct + '%';
                    }
                };
                xhr.onload = () => {
                    if (xhr.status === 200) {
                        try {
                            const data = JSON.parse(xhr.responseText);
                            resolve(data);
                        } catch (e) {
                            reject('INVALID SERVER RESPONSE');
                        }
                    } else {
                        try {
                            const data = JSON.parse(xhr.responseText);
                            reject(data.error || `HTTP ${xhr.status}`);
                        } catch (e) {
                            reject(`HTTP ${xhr.status}`);
                        }
                    }
                };
                xhr.onerror = () => reject('NETWORK ERROR');
            });

            xhr.open('POST', '/api/files/upload');
            xhr.setRequestHeader('X-Filename', file.name);
            xhr.send(file);

            await promise;
            statusEl.innerText = `SAVED ${file.name} OK`;
            statusEl.className = 'status success';
        } catch (e) {
            statusEl.innerText = `UPLOAD FAILED FOR ${file.name}: ${e}`;
            statusEl.className = 'status error';
            console.error("Upload error", e);
            break;
        }
    }

    progressBar.style.width = '0%';
    setTimeout(() => {
        progressContainer.style.display = 'none';
        statusEl.style.display = 'none';
        isUploading = false;
        console.log("Upload complete: resuming background polling");
        refreshFilesTab();
        refreshDriveSelects();
    }, 3000);
}

async function updateMonitorChannel() {
    const chan = document.getElementById('terminal-chan').value;
    const chanNum = safeInt(chan, -1);
    if (chanNum < -1 || chanNum > 31) {
        console.error("Invalid channel number:", chan);
        return;
    }
    try {
        const response = await fetch('/api/serial/monitor', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ chan: chanNum })
        });
        if (!response.ok) {
            console.error("Monitor channel API returned", response.status);
        }
        document.getElementById('terminal-output').innerHTML = '';
    } catch (e) {
        console.error("Failed to update monitor channel", e);
    }
}

async function pollStatus() {
    if (isUploading || _dialogOpen) {
        console.log("Skipping pollStatus during upload");
        return;
    }
    // Only poll if tab is visible
    const statusIdx = document.getElementById('tab-status').classList.contains('active');
    const termIdx = document.getElementById('tab-terminal').classList.contains('active');
    const driveIdx = document.getElementById('tab-drives').classList.contains('active');
    if (!statusIdx && !termIdx && !driveIdx) return;

    try {
        const response = await fetch('/api/status');
        if (!response.ok || _dialogOpen) return;
        const data = await response.json();
        if (!data || _dialogOpen) return;

        if (data.server_time) {
            document.getElementById('stat-time').innerText = data.server_time;
        }

        if (data.stats) {
            const opcode = data.stats.last_opcode;
            document.getElementById('stat-opcode').innerText =
                opcode != null ? '0x' + opcode.toString(16).toUpperCase() : '--';
            document.getElementById('stat-drive').innerText =
                data.stats.last_drive != null ? data.stats.last_drive : '--';

            // Serial activity (null-safe)
            const serContainer = document.getElementById('serial-activity-list');
            let serHtml = '';
            const serial = data.stats.serial || {};
            for (const [chan, stats] of Object.entries(serial)) {
                const tx = stats && stats.tx != null ? stats.tx : 0;
                const rx = stats && stats.rx != null ? stats.rx : 0;
                serHtml += `<div class="serial-stat-row">CH ${escHtml(chan)}: TX ${tx} | RX ${rx}</div>`;
            }
            if (!serHtml) serHtml = '<p>No activity.</p>';
            serContainer.innerHTML = serHtml;
        }

        if (data.logs && statusIdx) {
            const logBox = document.getElementById('system-log');
            // Use textContent-based approach to prevent XSS from log messages
            logBox.innerHTML = '';
            data.logs.forEach(l => {
                const line = document.createElement('div');
                line.textContent = '> ' + l;
                logBox.appendChild(line);
            });
            logBox.scrollTop = logBox.scrollHeight;
        }

        if (data.term_buf && termIdx) {
            const termBox = document.getElementById('terminal-output');
            if (data.term_buf.length > 0) {
                const text = bytesToString(data.term_buf);
                termBox.innerText = text;
                termBox.scrollTop = termBox.scrollHeight;
            }
        }

        if (data.monitor_chan !== undefined && termIdx) {
            const sel = document.getElementById('terminal-chan');
            if (sel.value != data.monitor_chan) sel.value = data.monitor_chan;
        }

        if (data.drive_stats) {
            // Track full paths of mounted files for the Files tab delete protection
            mountedFiles = data.drive_stats
                .filter(s => s && s.full_path)
                .map(s => s.full_path);

            if (driveIdx) renderDriveStats(data.drive_stats);
            // If we are currently on the files tab, we should refresh to update delete buttons
            // but maybe only if mountedFiles changed? For simplicity, we can refresh
            // if the list is visible and something changed.
        }

    } catch (e) {
        console.log("Status poll failed", e);
    }
}

function bytesToString(bytes) {
    if (!Array.isArray(bytes)) return '';
    let s = "";
    bytes.forEach(b => {
        if (typeof b !== 'number') return;
        // Simple printable check
        if (b === 10 || b === 13) s += "\n";
        else if (b >= 32 && b <= 126) s += String.fromCharCode(b);
        else s += "."; // Non-printable
    });
    return s;
}

function renderDriveStats(stats) {
    const grid = document.getElementById('drive-stats-grid');
    if (!grid) return;
    grid.innerHTML = '';

    if (!Array.isArray(stats)) return;

    stats.forEach((s, idx) => {
        if (!s) return;

        const totalReads = (s.read_hits || 0) + (s.read_misses || 0);
        const hitRate = totalReads > 0 ? (((s.read_hits || 0) / totalReads) * 100).toFixed(1) : 0;

        const card = document.createElement('div');
        card.className = 'card';
        card.innerHTML = `
            <h2>DRIVE ${idx}: ${escHtml(s.filename)}</h2>
            <div class="serial-stat-row">READ HITS: ${s.read_hits || 0}</div>
            <div class="serial-stat-row">READ MISSES: ${s.read_misses || 0}</div>
            <div class="serial-stat-row">HIT RATE: ${hitRate}%</div>
            <div class="serial-stat-row" style="margin-top:10px">TOTAL WRITES: ${s.write_count || 0}</div>
            <div class="serial-stat-row">DIRTY SECTORS: ${s.dirty_count || 0}</div>
        `;
        grid.appendChild(card);
    });
}

function renderSerialMap(map) {
    const container = document.getElementById('serial-map-container');
    container.innerHTML = '';

    if (!map || typeof map !== 'object') {
        container.innerHTML = '<p style="color:var(--coco-dark-green);">NO STATIONS CONFIGURED.</p>';
        return;
    }

    // Sort keys
    const channels = Object.keys(map).sort((a, b) => parseInt(a) - parseInt(b));

    channels.forEach(chan => {
        const entry = map[chan] || {};
        addSerialMapRow(chan, entry.host || '', entry.port || '', entry.mode || 'client');
    });

    if (channels.length === 0) {
        container.innerHTML = '<p style="color:var(--coco-dark-green);">NO STATIONS CONFIGURED.</p>';
    }
}

function addSerialMap() {
    const container = document.getElementById('serial-map-container');
    // Clear "No mappings" text if present
    if (container.querySelector('p')) container.innerHTML = '';
    addSerialMapRow('', '', '', 'client');
}

function addSerialMapRow(chan, host, port, mode) {
    const container = document.getElementById('serial-map-container');
    const div = document.createElement('div');
    div.className = 'serial-row';

    // Escape values before inserting into innerHTML
    const eChan = escHtml(chan);
    const eHost = escHtml(host);
    const ePort = escHtml(port);

    div.innerHTML = `
        <div style="flex:1">
            <label>CH</label>
            <input type="number" class="ser-chan" value="${eChan}" placeholder="0-14" min="0" max="31">
        </div>
        <div style="flex:1">
            <label>MODE</label>
            <select class="ser-mode">
                <option value="client" ${mode === 'client' ? 'selected' : ''}>CLIENT</option>
                <option value="server" ${mode === 'server' ? 'selected' : ''}>SERVER</option>
            </select>
        </div>
        <div style="flex:2">
            <label>HOST / IP</label>
            <input type="text" class="ser-host" value="${eHost}" placeholder="HOST OR 0.0.0.0">
        </div>
        <div style="flex:1">
            <label>PORT</label>
            <input type="number" class="ser-port" value="${ePort}" placeholder="PORT" min="1" max="65535">
        </div>
        <div style="display:flex; align-items:flex-end;">
             <button class="btn btn-danger" onclick="this.parentElement.parentElement.remove()">X</button>
        </div>
    `;
    container.appendChild(div);
}

function showStatus(msg, type) {
    const el = document.getElementById('status-msg');
    el.textContent = msg;
    el.className = 'status ' + type;
    el.style.display = 'block';
    setTimeout(() => el.style.display = 'none', 5000);
}

async function saveConfig() {
    // Validate numeric inputs with safe fallbacks
    const baudRate = safeInt(document.getElementById('baud').value, 115200);
    const tzOffset = safeInt(document.getElementById('tz_offset').value, 0);
    const sdSpiId = safeInt(document.getElementById('sd_spi_id').value, 1);
    const sdSck = safeInt(document.getElementById('sd_sck').value, 10);
    const sdMosi = safeInt(document.getElementById('sd_mosi').value, 11);
    const sdMiso = safeInt(document.getElementById('sd_miso').value, 12);
    const sdCs = safeInt(document.getElementById('sd_cs').value, 13);

    // Validate ranges
    if (tzOffset < -12 || tzOffset > 14) {
        showStatus('Timezone offset must be -12 to +14', 'error');
        return;
    }
    if (sdSck < 0 || sdSck > 28 || sdMosi < 0 || sdMosi > 28 ||
        sdMiso < 0 || sdMiso > 28 || sdCs < 0 || sdCs > 28) {
        showStatus('GPIO pins must be 0-28', 'error');
        return;
    }

    const data = {
        baud_rate: baudRate,
        wifi_ssid: document.getElementById('ssid').value,
        wifi_password: document.getElementById('wifi_pass').value,
        ntp_server: document.getElementById('ntp_server').value,
        timezone_offset: tzOffset,
        drives: [],
        serial_map: {},
        // SD card SPI config
        sd_spi_id: sdSpiId,
        sd_sck: sdSck,
        sd_mosi: sdMosi,
        sd_miso: sdMiso,
        sd_cs: sdCs,
        sd_mount_point: document.getElementById('sd_mount_point').value.trim() || '/sd'
    };

    for (let i = 0; i < 4; i++) {
        const val = document.getElementById(`drive_${i}`).value.trim();
        data.drives.push(val === '' ? null : val);
    }

    // Harvest Serial Map with validation
    const rows = document.querySelectorAll('.serial-row');
    let serialValid = true;
    rows.forEach(row => {
        const chanEl = row.querySelector('.ser-chan');
        const modeEl = row.querySelector('.ser-mode');
        const hostEl = row.querySelector('.ser-host');
        const portEl = row.querySelector('.ser-port');
        if (!chanEl || !modeEl || !hostEl || !portEl) return;

        const chan = chanEl.value;
        const mode = modeEl.value;
        let host = hostEl.value.trim();
        const portNum = safeInt(portEl.value, 0);

        // If server mode and host is blank, default to 0.0.0.0
        if (mode === 'server' && host === '') {
            host = '0.0.0.0';
        }

        // Validate port range
        if (chan !== '' && host !== '' && portNum > 0) {
            if (portNum < 1 || portNum > 65535) {
                serialValid = false;
                return;
            }
            const chanNum = safeInt(chan, -1);
            if (chanNum < 0 || chanNum > 31) {
                serialValid = false;
                return;
            }
            data.serial_map[chan] = { host: host, port: portNum, mode: mode };
        }
    });

    if (!serialValid) {
        showStatus('Invalid serial config: port 1-65535, channel 0-31', 'error');
        return;
    }

    try {
        const response = await fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        if (!response.ok) {
            showStatus('Server error: HTTP ' + response.status, 'error');
            return;
        }
        const result = await response.json();
        if (result.status === 'ok') {
            showStatus('Configuration saved successfully!', 'success');
        } else {
            showStatus('Error saving: ' + (result.message || 'Unknown error'), 'error');
        }
    } catch (error) {
        console.error('Error:', error);
        showStatus('Network error while saving.', 'error');
    }
}

async function pollSdStatus() {
    if (isUploading || _dialogOpen) {
        console.log("Skipping pollSdStatus during upload");
        return;
    }
    try {
        const response = await fetch('/api/sd/status');
        if (!response.ok || _dialogOpen) return;
        const data = await response.json();
        if (!data || _dialogOpen) return;

        // Update config page indicator
        const configIndicator = document.getElementById('sd-config-indicator');
        if (configIndicator) {
            if (data.mounted) {
                let text = `\uD83D\uDFE2 MOUNTED AT ${escHtml(data.mount_point)}`;
                if (data.free_mb != null) {
                    text += ` | ${data.free_mb} MB FREE / ${data.total_mb} MB`;
                }
                configIndicator.innerHTML = text;
                configIndicator.style.color = 'var(--coco-green)';
            } else {
                configIndicator.innerHTML = '\uD83D\uDD34 NOT MOUNTED (NO CARD OR WRONG PINS)';
                configIndicator.style.color = 'var(--coco-alert)';
            }
        }

        // Update dashboard indicator
        const dashStatus = document.getElementById('sd-card-status');
        if (dashStatus) {
            if (data.mounted) {
                let html = `<div class="status-grid">`;
                html += `<div>STATUS: <span class="highlight">MOUNTED</span></div>`;
                html += `<div>PATH: <span class="highlight">${escHtml(data.mount_point)}</span></div>`;
                if (data.free_mb != null) {
                    html += `<div>FREE: <span class="highlight">${data.free_mb} MB</span></div>`;
                    html += `<div>TOTAL: <span class="highlight">${data.total_mb} MB</span></div>`;
                }
                if (data.files_found != null) {
                    html += `<div>DSK FILES: <span class="highlight">${data.files_found}</span></div>`;
                }
                html += `</div>`;
                dashStatus.innerHTML = html;
            } else {
                dashStatus.innerHTML = '<span style="color:var(--coco-alert);">\uD83D\uDD34 NO SD CARD DETECTED</span>';
            }
        }
    } catch (e) {
        console.log('SD status poll failed', e);
    }
}

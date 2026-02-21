document.addEventListener('DOMContentLoaded', init);

async function fetchConfig() {
    try {
        const response = await fetch('/api/config');
        return await response.json();
    } catch (e) {
        console.error("Failed to fetch config", e);
        return {};
    }
}

async function fetchFiles() {
    try {
        const response = await fetch('/api/files');
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

    // Build options with filename display and storage badge
    let baseOptions = '<option value="">(NO DISK)</option>';
    files.forEach(f => {
        const fname = f.split('/').pop();
        const badge = f.startsWith('/sd') ? '\uD83D\uDCBE' : '\uD83D\uDCC1';
        baseOptions += `<option value="${f}">${badge} ${fname}</option>`;
    });

    for (let i = 0; i < 4; i++) {
        const div = document.createElement('div');
        const currentVal = currentDrives[i] || '';

        // Ensure current value is in the list
        let options = baseOptions;
        if (currentVal && !files.includes(currentVal)) {
            const missingName = currentVal.split('/').pop();
            options += `<option value="${currentVal}">\u26A0 ${missingName} (MISSING)</option>`;
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

    // Start Polling
    setInterval(pollStatus, 1000);  // 1 second for live time + heartbeat
    setInterval(pollSdStatus, 10000);  // SD status every 10s
}

function switchTab(tabName) {
    // Hide all tabs
    document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));

    // Show selected
    document.getElementById(`tab-${tabName}`).classList.add('active');

    // Button style
    const btns = document.querySelectorAll('.tab-btn');
    if (tabName === 'config') btns[0].classList.add('active');
    if (tabName === 'status') btns[1].classList.add('active');
    if (tabName === 'terminal') btns[2].classList.add('active');
    if (tabName === 'drives') btns[3].classList.add('active');
}

async function updateMonitorChannel() {
    const chan = document.getElementById('terminal-chan').value;
    try {
        await fetch('/api/serial/monitor', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ chan: parseInt(chan) })
        });
        document.getElementById('terminal-output').innerHTML = '';
    } catch (e) {
        console.error("Failed to update monitor channel", e);
    }
}

async function pollStatus() {
    // Only poll if tab is visible
    const statusIdx = document.getElementById('tab-status').classList.contains('active');
    const termIdx = document.getElementById('tab-terminal').classList.contains('active');
    const driveIdx = document.getElementById('tab-drives').classList.contains('active');
    if (!statusIdx && !termIdx && !driveIdx) return;

    try {
        const response = await fetch('/api/status');
        const data = await response.json();

        if (data.server_time) {
            document.getElementById('stat-time').innerText = data.server_time;
        }

        if (data.stats) {
            document.getElementById('stat-opcode').innerText = '0x' + data.stats.last_opcode.toString(16).toUpperCase();
            document.getElementById('stat-drive').innerText = data.stats.last_drive;

            // Serial
            const serContainer = document.getElementById('serial-activity-list');
            let serHtml = '';
            for (const [chan, stats] of Object.entries(data.stats.serial)) {
                serHtml += `<div class="serial-stat-row">CH ${chan}: TX ${stats.tx} | RX ${stats.rx}</div>`;
            }
            if (!serHtml) serHtml = '<p>No activity.</p>';
            serContainer.innerHTML = serHtml;
        }

        if (data.logs && statusIdx) {
            const logBox = document.getElementById('system-log');
            logBox.innerHTML = data.logs.map(l => `<div>> ${l}</div>`).join('');
            logBox.scrollTop = logBox.scrollHeight;
        }

        if (data.term_buf && termIdx) {
            const termBox = document.getElementById('terminal-output');
            if (data.term_buf.length > 0) {
                // Convert bytes to string (escaping HTML)
                const text = bytesToString(data.term_buf);
                // Simple append or replacement? 
                // Since the server buffer is only 512 bytes and we clear locally,
                // let's just refresh.
                termBox.innerText = text;
                termBox.scrollTop = termBox.scrollHeight;
            }
        }

        if (data.monitor_chan !== undefined && termIdx) {
            const sel = document.getElementById('terminal-chan');
            if (sel.value != data.monitor_chan) sel.value = data.monitor_chan;
        }

        if (data.drive_stats && driveIdx) {
            renderDriveStats(data.drive_stats);
        }

    } catch (e) {
        console.log("Status poll failed", e);
    }
}

function bytesToString(bytes) {
    let s = "";
    bytes.forEach(b => {
        // Simple printable check
        if (b === 10 || b === 13) s += "\n";
        else if (b >= 32 && b <= 126) s += String.fromCharCode(b);
        else s += "."; // Non-printable
    });
    return s;
}

function renderDriveStats(stats) {
    const grid = document.getElementById('drive-stats-grid');
    grid.innerHTML = '';

    stats.forEach((s, idx) => {
        if (!s) return;

        const totalReads = s.read_hits + s.read_misses;
        const hitRate = totalReads > 0 ? ((s.read_hits / totalReads) * 100).toFixed(1) : 0;

        const card = document.createElement('div');
        card.className = 'card';
        card.innerHTML = `
            <h2>DRIVE ${idx}: ${s.filename}</h2>
            <div class="serial-stat-row">READ HITS: ${s.read_hits}</div>
            <div class="serial-stat-row">READ MISSES: ${s.read_misses}</div>
            <div class="serial-stat-row">HIT RATE: ${hitRate}%</div>
            <div class="serial-stat-row" style="margin-top:10px">TOTAL WRITES: ${s.write_count}</div>
            <div class="serial-stat-row">DIRTY SECTORS: ${s.dirty_count}</div>
        `;
        grid.appendChild(card);
    });
}

function renderSerialMap(map) {
    const container = document.getElementById('serial-map-container');
    container.innerHTML = '';

    // Sort keys
    const channels = Object.keys(map).sort((a, b) => parseInt(a) - parseInt(b));

    channels.forEach(chan => {
        addSerialMapRow(chan, map[chan].host, map[chan].port, map[chan].mode || 'client');
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
    // Inline flex layout is now handled by .serial-row CSS, but we keep the structure
    div.className = 'serial-row';

    div.innerHTML = `
        <div style="flex:1">
            <label>CH</label>
            <input type="number" class="ser-chan" value="${chan}" placeholder="0-14">
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
            <input type="text" class="ser-host" value="${host}" placeholder="HOST OR 0.0.0.0">
        </div>
        <div style="flex:1">
            <label>PORT</label>
            <input type="number" class="ser-port" value="${port}" placeholder="PORT">
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
    const data = {
        baud_rate: parseInt(document.getElementById('baud').value),
        wifi_ssid: document.getElementById('ssid').value,
        wifi_password: document.getElementById('wifi_pass').value,
        ntp_server: document.getElementById('ntp_server').value,
        timezone_offset: parseInt(document.getElementById('tz_offset').value),
        drives: [],
        serial_map: {},
        // SD card SPI config
        sd_spi_id: parseInt(document.getElementById('sd_spi_id').value),
        sd_sck: parseInt(document.getElementById('sd_sck').value),
        sd_mosi: parseInt(document.getElementById('sd_mosi').value),
        sd_miso: parseInt(document.getElementById('sd_miso').value),
        sd_cs: parseInt(document.getElementById('sd_cs').value),
        sd_mount_point: document.getElementById('sd_mount_point').value.trim() || '/sd'
    };

    for (let i = 0; i < 4; i++) {
        const val = document.getElementById(`drive_${i}`).value.trim();
        data.drives.push(val === '' ? null : val);
    }

    // Harvest Serial Map
    const rows = document.querySelectorAll('.serial-row');
    rows.forEach(row => {
        const chan = row.querySelector('.ser-chan').value;
        const mode = row.querySelector('.ser-mode').value;
        let host = row.querySelector('.ser-host').value.trim();
        const port = row.querySelector('.ser-port').value;

        // If server mode and host is blank, default to 0.0.0.0
        if (mode === 'server' && host === '') {
            host = '0.0.0.0';
        }

        if (chan !== '' && host !== '' && port !== '') {
            data.serial_map[chan] = { host: host, port: parseInt(port), mode: mode };
        }
    });

    try {
        const response = await fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        const result = await response.json();
        if (result.status === 'ok') {
            showStatus('Configuration saved successfully!', 'success');
        } else {
            showStatus('Error saving: ' + result.message, 'error');
        }
    } catch (error) {
        console.error('Error:', error);
        showStatus('Network error while saving.', 'error');
    }
}

async function pollSdStatus() {
    try {
        const response = await fetch('/api/sd/status');
        const data = await response.json();

        // Update config page indicator
        const configIndicator = document.getElementById('sd-config-indicator');
        if (configIndicator) {
            if (data.mounted) {
                let text = `\uD83D\uDFE2 MOUNTED AT ${data.mount_point}`;
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
                html += `<div>PATH: <span class="highlight">${data.mount_point}</span></div>`;
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

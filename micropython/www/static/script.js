document.addEventListener('DOMContentLoaded', init);
const VALID_TABS = ['config', 'status', 'terminal', 'drives', 'files'];

window.addEventListener('hashchange', () => {
    const hash = window.location.hash.replace('#', '');
    if (VALID_TABS.includes(hash)) {
        switchTab(hash, false);
    }
});

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
    // Check initial hash before doing async work to prevent UI flashing
    const initialHash = window.location.hash.replace('#', '');
    if (VALID_TABS.includes(initialHash)) {
        switchTab(initialHash, false);
    } else {
        history.replaceState(null, null, '#config');
        switchTab('config', false);
    }

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
    document.getElementById('wdt_enabled').checked = !!config.wdt_enabled;
    document.getElementById('log_level').value = config.log_level != null ? config.log_level : 1;

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
    renderRemoteServers(config.remote_servers || []);

    // Fetch remote files and wait for them, then rebuild dropdown options so they include remote drives
    await fetchRemoteFiles();
    refreshDriveSelects();
    await new Promise(r => setTimeout(r, 500)); // Socket TIME_WAIT cooldown

    // Check SD card status on load
    pollSdStatus();

    // Initialize File Manager listeners
    initFilesTab();

    // Automatically test each configured remote server connection on startup
    // Serialize tests to avoid concurrent socket allocation on the Pico W
    const remoteTestBtns = document.querySelectorAll('#remote-servers-container .remote-row .btn-action');
    for (const btn of remoteTestBtns) {
        await testRemoteServer(btn);
        await new Promise(r => setTimeout(r, 200)); // GC breathing room
    }

    // Start Polling (Adaptive & Optimized)
    setInterval(pollHeartbeat, 1000); // 1s heartbeat for live time + connectivity
    setInterval(pollAdaptive, 3000);  // 3s for tab-specific data (stats, terminal, logs)
    setInterval(pollSdStatus, 15000); // 15s for SD status

    // Attach listeners for dirty state tracking on the config form
    const configTab = document.getElementById('tab-config');
    if (configTab) {
        configTab.addEventListener('input', markConfigDirty);
        configTab.addEventListener('change', markConfigDirty);
    }

    // Config just loaded from server, clear dirty state
    clearConfigDirty();

    // Allow switchTab to trigger heavy refreshes now that init is done
    _initComplete = true;

    // If the initial tab was 'files', now do the heavy refresh
    if (VALID_TABS.includes(initialHash) && initialHash === 'files') {
        refreshFilesTab();
    }
}

function markConfigDirty() {
    if (configDirty) return;
    configDirty = true;
    const btn = document.getElementById('btn-save-config');
    const stickyWarning = document.getElementById('sticky-unsaved-warning');
    const bottomWarning = document.getElementById('bottom-unsaved-warning');
    if (btn) btn.classList.add('btn-unsaved');
    if (stickyWarning) stickyWarning.style.display = 'block';
    if (bottomWarning) bottomWarning.style.display = 'block';
}

function clearConfigDirty() {
    configDirty = false;
    const btn = document.getElementById('btn-save-config');
    const stickyWarning = document.getElementById('sticky-unsaved-warning');
    const bottomWarning = document.getElementById('bottom-unsaved-warning');
    if (btn) btn.classList.remove('btn-unsaved');
    if (stickyWarning) stickyWarning.style.display = 'none';
    if (bottomWarning) bottomWarning.style.display = 'none';
}

async function revertConfig() {
    const confirmed = await customConfirm("ARE YOU SURE YOU WANT TO REVERT ALL UNSAVED CHANGES?");
    if (confirmed) {
        // Re-initialize the form from the server state
        await init();
        // init() automatically calls clearConfigDirty() at the end
    }
}

let mountedFiles = [];
let _driveAssignments = [null, null, null, null]; // Indexed by drive number
let _pollInFlight = false;  // Global guard: only one poll/fetch at a time
let _remoteInFlight = false;  // Guard: only one remote file fetch at a time
let _initComplete = false;  // Suppress heavy tab refreshes during init
let isUploading = false;
let configDirty = false;
let _dialogOpen = false;
let _remoteFiles = [];    // Cached remote file list
let _cloneServerUrl = ''; // For clone modal
let _cloneDiskName = '';  // For clone modal
let terminalOffset = 0;   // Track incremental terminal data
let logOffset = 0;        // Track incremental logs
let _heartbeatInFlight = false;
let _statsInFlight = false;
let _termInFlight = false;
let _logsInFlight = false;

function switchTab(tabName, updateHash = true) {
    if (!VALID_TABS.includes(tabName)) return;

    if (updateHash && window.location.hash !== '#' + tabName) {
        window.location.hash = tabName;
        return; // Let the hashchange event trigger the UI update to avoid double-execution
    }

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

    if (tabName === 'files' && _initComplete) {
        refreshFilesTab();
    }
    if (tabName === 'drives') {
        refreshDriveSelects();
    }
}

async function refreshDriveSelects(cachedFiles) {
    const files = cachedFiles || await fetchFiles();
    const safeFiles = Array.isArray(files) ? files : [];

    // Build fresh options
    let baseOptions = '<option value="">(NO DISK)</option>';
    safeFiles.forEach(f => {
        const fname = String(f).split('/').pop();
        const badge = String(f).startsWith('/sd') ? '\uD83D\uDCBE' : '\uD83D\uDCC1';
        baseOptions += `<option value="${escHtml(f)}">${badge} ${escHtml(fname)}</option>`;
    });

    // Add remote files with globe icon
    _remoteFiles.forEach(rf => {
        const driveUrl = rf.url.replace(/\/$/, '') + '/disk/' + rf.name;
        baseOptions += `<option value="${escHtml(driveUrl)}">\uD83C\uDF10 [${escHtml(rf.server)}] ${escHtml(rf.name)}</option>`;
    });

    for (let i = 0; i < 4; i++) {
        const sel = document.getElementById(`drive_${i}`);
        if (!sel) continue;
        const currentVal = sel.value;

        let options = baseOptions;
        if (currentVal && !safeFiles.includes(currentVal)) {
            // Check if it's a known remote URL
            const isRemoteKnown = _remoteFiles.some(rf => {
                const driveUrl = rf.url.replace(/\/$/, '') + '/disk/' + rf.name;
                return driveUrl === currentVal;
            });
            if (!isRemoteKnown && currentVal.startsWith('http')) {
                const missingName = String(currentVal).split('/').pop();
                options += `<option value="${escHtml(currentVal)}">\uD83C\uDF10 ${escHtml(missingName)}</option>`;
            } else if (!isRemoteKnown) {
                const missingName = String(currentVal).split('/').pop();
                options += `<option value="${escHtml(currentVal)}">\u26A0 ${escHtml(missingName)} (MISSING)</option>`;
            }
        }

        sel.innerHTML = options;
        sel.value = currentVal;
    }
}

async function refreshFilesTab() {
    if (_pollInFlight) return; // Don't pile on requests
    _pollInFlight = true;

    const listBody = document.getElementById('files-list');
    listBody.innerHTML = '<tr><td colspan="2">LOADING FILES...</td></tr>';

    // First fetch status to ensure mountedFiles is up-to-date
    try {
        const statusRes = await fetch('/api/status');
        if (statusRes.ok) {
            const data = await statusRes.json();
            if (data && data.drive_stats) {
                mountedFiles = data.drive_stats
                    .filter(s => s && s.full_path)
                    .map(s => s.full_path);
                _driveAssignments = data.drive_stats.map(s => s && s.full_path ? s.full_path : null);
            }
        }
    } catch (e) { console.warn("Failed to update mount status", e); }

    const files = await fetchFiles();
    // Fetch optional file metadata (mtime, size) — non-blocking
    let fileInfo = {};
    try {
        const infoRes = await fetch('/api/files/info');
        if (infoRes.ok) fileInfo = await infoRes.json();
    } catch (e) { /* metadata is optional */ }

    listBody.innerHTML = '';

    if (!files || files.length === 0) {
        listBody.innerHTML = '<tr><td colspan="2">NO DISK IMAGES FOUND.</td></tr>';
    } else {
        // Only show files on SD or root that are .dsk
        files.forEach(f => {
            const tr = document.createElement('tr');
            const fname = f.split('/').pop();
            const isMounted = mountedFiles.includes(f);
            const meta = fileInfo[f];
            const mtimeStr = meta && meta.mtime ? meta.mtime : '';
            const sizeKb = meta && meta.size ? (meta.size / 1024).toFixed(1) + ' KB' : '';
            const subtitle = [sizeKb, mtimeStr].filter(Boolean).join(' \u2022 ');

            tr.innerHTML = `
                <td class="filename-cell" title="${escHtml(f)}${mtimeStr ? '\nModified: ' + escHtml(mtimeStr) : ''}">
                    <div style="display: flex; align-items: baseline; gap: 8px;">
                        <span class="file-icon">${f.startsWith('/sd') ? '\uD83D\uDCBE' : '\uD83D\uDCC1'}</span>
                        <span style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${escHtml(fname)}</span>
                    </div>
                    ${subtitle ? '<div style="font-size:0.7em; color:var(--coco-dark-green); margin-left:30px;">' + escHtml(subtitle) + '</div>' : ''}
                </td>
                <td class="action-col">
                    <div class="lane-wrapper">
                        <div class="lane-status"></div>
                        <div class="lane-primary"></div>
                        <div class="lane-secondary"></div>
                    </div>
                </td>
            `;

            const statusLane = tr.querySelector('.lane-status');
            const primaryLane = tr.querySelector('.lane-primary');
            const secondaryLane = tr.querySelector('.lane-secondary');

            if (isMounted) {
                const statusSpan = document.createElement('span');
                statusSpan.className = 'in-use-indicator';
                statusSpan.style.color = 'var(--coco-alert)';
                statusSpan.style.fontWeight = 'bold';
                statusSpan.style.fontSize = '0.9em';
                statusSpan.textContent = '[IN USE]';
                statusLane.appendChild(statusSpan);

                const dlBtn = document.createElement('button');
                dlBtn.className = 'btn btn-action btn-disabled';
                dlBtn.textContent = 'DOWNLOAD';
                dlBtn.title = 'Cannot download mounted image';
                primaryLane.appendChild(dlBtn);
            } else {
                const dlBtn = document.createElement('button');
                dlBtn.className = 'btn btn-action btn-primary';
                dlBtn.textContent = 'DOWNLOAD';
                dlBtn.onclick = () => {
                    window.location.href = `/api/files/download?path=${encodeURIComponent(f)}`;
                };
                primaryLane.appendChild(dlBtn);

                const deleteBtn = document.createElement('button');
                deleteBtn.className = 'btn btn-action btn-danger';
                deleteBtn.textContent = 'DELETE';
                deleteBtn.onclick = () => deleteFile(f);
                secondaryLane.appendChild(deleteBtn);
            }

            listBody.appendChild(tr);
        });
    }

    // Remote files section
    const remoteListBody = document.getElementById('remote-files-list');
    if (remoteListBody) {
        await fetchRemoteFiles();
        remoteListBody.innerHTML = '';

        if (_remoteFiles.length === 0) {
            remoteListBody.innerHTML = '<tr><td colspan="3">NO REMOTE SERVERS CONFIGURED.</td></tr>';
        } else {
            _remoteFiles.forEach(rf => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td class="filename-cell" title="${escHtml(rf.name)}">
                        <span class="file-icon">\uD83C\uDF10</span> ${escHtml(rf.name)}
                    </td>
                    <td><span class="remote-badge remote-badge-name">${escHtml(rf.server)}</span></td>
                    <td class="action-col">
                        <div class="lane-wrapper">
                            <div class="lane-status"></div>
                            <div class="lane-primary"></div>
                            <div class="lane-secondary"></div>
                        </div>
                    </td>
                `;

                const cloneBtn = document.createElement('button');
                cloneBtn.className = 'btn btn-action btn-primary';
                cloneBtn.textContent = 'CLONE';
                cloneBtn.title = 'Clone to local SD card';
                cloneBtn.onclick = () => showCloneModal(rf.url, rf.name, rf.server);
                tr.querySelector('.lane-primary').appendChild(cloneBtn);

                remoteListBody.appendChild(tr);
            });
        }
    }

    _pollInFlight = false;
}

async function customConfirm(message) {
    return new Promise(resolve => {
        const overlay = document.getElementById('custom-confirm');
        const msgEl = document.getElementById('confirm-msg');
        const btnYes = document.getElementById('confirm-yes');
        const btnNo = document.getElementById('confirm-no');

        msgEl.textContent = message;
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

async function customAlert(message) {
    return new Promise(resolve => {
        const overlay = document.getElementById('custom-alert');
        const msgEl = document.getElementById('alert-msg');
        const btnOk = document.getElementById('alert-ok');

        msgEl.textContent = message;
        overlay.style.display = 'flex';
        _dialogOpen = true;

        btnOk.onclick = () => {
            overlay.style.display = 'none';
            _dialogOpen = false;
            btnOk.onclick = null;
            resolve();
        };
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
            await customAlert('DELETE FAILED:\n\n' + result.error);
        }
    } catch (e) {
        await customAlert('DELETE FAILED:\n\n' + e);
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
            statusEl.textContent = `SKIPPING ${file.name}: ONLY .DSK ALLOWED`;
            statusEl.classList.add('error');
            continue;
        }

        // Check if file is currently "In Use" (regression protection)
        const isMounted = mountedFiles.some(f => f.split('/').pop() === file.name);
        if (isMounted) {
            const confirmed = await customConfirm(`WARNING: ${file.name} IS CURRENTLY [IN USE].\nOVERWRITING MAY CRASH THE COCO.\n\nPROCEED ANYWAY?`);
            if (!confirmed) {
                statusEl.textContent = `SKIPPED ${file.name} (IN USE)`;
                continue;
            }
        }

        try {
            const xhr = new XMLHttpRequest();
            let uploadPollTimeoutId; // Use a single ID for setTimeout

            const promise = new Promise((resolve, reject) => {
                // Remove xhr.upload.onprogress to avoid browser TCP buffering jumps

                // Poll for progress using recursive setTimeout to avoid overlapping requests
                let pollInFlight = false;
                let uploadDone = false;
                const pollUploadStatus = async () => {
                    if (uploadDone || pollInFlight) return;
                    pollInFlight = true;
                    try {
                        const response = await fetch('/api/files/upload_status');
                        if (response.ok) {
                            const data = await response.json();
                            if (data.total > 0) {
                                const pct = (data.written / data.total) * 100;
                                progressBar.style.width = pct + '%';
                                statusEl.textContent = `UPLOADING: ${Math.round(pct)}% (${Math.round(data.written / 1024)}KB / ${Math.round(data.total / 1024)}KB)`;

                                if (data.written >= data.total) {
                                    clearTimeout(uploadPollTimeoutId);
                                    // The XHR onload will handle the final resolve/reject
                                    return;
                                }
                            }
                        }
                    } catch (e) {
                        // Ignore polling errors, let the XHR error handler deal with fatal network issues
                        console.warn("Upload status poll failed", e);
                    } finally {
                        pollInFlight = false;
                        uploadPollTimeoutId = setTimeout(pollUploadStatus, 1000); // Schedule next poll
                    }
                };

                // Start initial poll
                uploadPollTimeoutId = setTimeout(pollUploadStatus, 1000);


                xhr.onload = () => {
                    uploadDone = true;
                    clearTimeout(uploadPollTimeoutId);
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

                xhr.onerror = () => {
                    uploadDone = true;
                    clearTimeout(uploadPollTimeoutId);
                    reject('NETWORK ERROR');
                };
            });

            xhr.open('POST', '/api/files/upload');
            xhr.setRequestHeader('X-Filename', file.name);
            xhr.send(file);

            await promise;
            statusEl.textContent = `SAVED ${file.name} OK`;
            statusEl.className = 'status success';
        } catch (e) {
            statusEl.textContent = `UPLOAD FAILED FOR ${file.name}: ${e}`;
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

async function pollHeartbeat() {
    if (isUploading || _dialogOpen || _heartbeatInFlight) return;
    _heartbeatInFlight = true;
    try {
        const response = await fetch('/api/status/heartbeat');
        if (!response.ok) return;
        const data = await response.json();
        if (data.server_time) {
            document.getElementById('stat-time').textContent = data.server_time;
        }
        if (data.last_opcode != null) {
            document.getElementById('stat-opcode').textContent = '0x' + data.last_opcode.toString(16).toUpperCase();
        }
        // Small visual activity indicator could go here
    } catch (e) {
    } finally {
        _heartbeatInFlight = false;
    }
}

async function pollAdaptive() {
    if (isUploading || _dialogOpen) return;

    const statusActive = document.getElementById('tab-status').classList.contains('active');
    const termActive = document.getElementById('tab-terminal').classList.contains('active');
    const driveActive = document.getElementById('tab-drives').classList.contains('active');

    // 1. Stats Polling (Status or Drives tab)
    if ((statusActive || driveActive) && !_statsInFlight) {
        _statsInFlight = true;
        try {
            const res = await fetch('/api/status/stats');
            if (res.ok) {
                const data = await res.json();
                if (data.protocol_stats) {
                    document.getElementById('stat-opcode').textContent = 
                        data.protocol_stats.last_opcode != null ? '0x' + data.protocol_stats.last_opcode.toString(16).toUpperCase() : '--';
                    document.getElementById('stat-drive').textContent = 
                        data.protocol_stats.last_drive != null ? data.protocol_stats.last_drive : '--';
                        
                    const serContainer = document.getElementById('serial-activity-list');
                    let serHtml = '';
                    for (const [chan, stats] of Object.entries(data.serial || {})) {
                        serHtml += `<div class="serial-stat-row">CH ${escHtml(chan)}: TX ${stats.tx} | RX ${stats.rx}</div>`;
                    }
                    serContainer.innerHTML = serHtml || '<p>No activity.</p>';
                }
                if (data.drive_stats) {
                    mountedFiles = data.drive_stats.filter(s => s && s.full_path).map(s => s.full_path);
                    _driveAssignments = data.drive_stats.map(s => s && s.full_path ? s.full_path : null);
                    if (driveActive) renderDriveStats(data.drive_stats);
                }
            }
        } finally { _statsInFlight = false; }
    }

    // 2. Terminal Polling (Delta)
    if (termActive && !_termInFlight) {
        _termInFlight = true;
        try {
            const res = await fetch(`/api/status/terminal?offset=${terminalOffset}`);
            if (res.ok) {
                const data = await res.json();
                if (data.data && data.data.length > 0) {
                    const termBox = document.getElementById('terminal-output');
                    const text = bytesToString(data.data);
                    // Append for incremental, though based on bytesToString logic we might need refinement
                    // If bytesToString is simple printable check, we should append to innerText
                    termBox.innerText += text;
                    // Limit total characters in DOM
                    if (termBox.innerText.length > 10000) {
                        termBox.innerText = termBox.innerText.slice(-5000);
                    }
                    termBox.scrollTop = termBox.scrollHeight;
                }
                terminalOffset = data.offset;
                if (data.monitor_chan !== undefined) {
                    const sel = document.getElementById('terminal-chan');
                    if (sel.value != data.monitor_chan) sel.value = data.monitor_chan;
                }
            }
        } finally { _termInFlight = false; }
    }

    // 3. Logs Polling (Delta)
    if (statusActive && !_logsInFlight) {
        _logsInFlight = true;
        try {
            const res = await fetch(`/api/status/logs?offset=${logOffset}`);
            if (res.ok) {
                const data = await res.json();
                if (data.logs && data.logs.length > 0) {
                    const logBox = document.getElementById('system-log');
                    data.logs.forEach(l => {
                        const line = document.createElement('div');
                        line.textContent = '> ' + l;
                        logBox.appendChild(line);
                    });
                    logBox.scrollTop = logBox.scrollHeight;
                    // Keep DOM small
                    while (logBox.children.length > 50) logBox.removeChild(logBox.firstChild);
                }
                logOffset = data.offset;
            }
        } finally { _logsInFlight = false; }
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

        const totalDirReads = (s.dir_cache_hits || 0) + (s.dir_cache_misses || 0);
        const dirHitRate = totalDirReads > 0 ? (((s.dir_cache_hits || 0) / totalDirReads) * 100).toFixed(1) : 0;

        const isRemote = s.is_remote || false;
        const icon = isRemote ? '\uD83C\uDF10' : '';
        const modeBadge = isRemote
            ? '<span class="remote-badge" style="margin-left:10px;">READ-ONLY</span>'
            : '';

        const card = document.createElement('div');
        card.className = 'card';
        card.innerHTML = `
            <h2>DRIVE ${idx}: ${icon} ${escHtml(s.filename)}${modeBadge}</h2>
            ${s.mtime ? '<div class="serial-stat-row" style="color:var(--coco-dark-green); font-size:0.85em;">MODIFIED: ' + escHtml(s.mtime) + '</div>' : ''}
            <div class="serial-stat-row">READ HITS: ${s.read_hits || 0}</div>
            <div class="serial-stat-row">READ MISSES: ${s.read_misses || 0}</div>
            <div class="serial-stat-row">HIT RATE: ${hitRate}%</div>
            
            <div class="serial-stat-row" style="margin-top:10px; color:var(--coco-bright-green); font-weight:bold;">\uD83D\uDCC1 RBF DIR CACHE:</div>
            <div class="serial-stat-row">DIR HITS: ${s.dir_cache_hits || 0}</div>
            <div class="serial-stat-row">DIR MISSES: ${s.dir_cache_misses || 0}</div>
            <div class="serial-stat-row">DIR HIT RATE: ${dirHitRate}%</div>
            <div class="serial-stat-row">DIR CACHE SIZE: ${s.dir_cache_size || 0} SECTORS</div>

            <div class="serial-stat-row">LATENCY: ${s.latency_us ? s.latency_us + ' \u00B5s' : '--'}</div>
            <div class="serial-stat-row" style="margin-top:10px">TOTAL WRITES: ${s.write_count || 0}</div>
            <div class="serial-stat-row">DIRTY SECTORS: ${s.dirty_count || 0}</div>
        `;

        // Add clone button for remote drives
        if (isRemote) {
            const cloneBtn = document.createElement('button');
            cloneBtn.className = 'btn btn-secondary';
            cloneBtn.style.marginTop = '15px';
            cloneBtn.textContent = 'CLONE TO LOCAL';
            cloneBtn.onclick = () => {
                // Parse server URL from drive filename
                const url = s.full_path;
                const parts = url.split('/disk/');
                if (parts.length === 2) {
                    showCloneModal(parts[0], parts[1], '', idx);
                }
            };
            card.appendChild(cloneBtn);
        }

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
        remote_servers: [],
        // SD card SPI config
        sd_spi_id: sdSpiId,
        sd_sck: sdSck,
        sd_mosi: sdMosi,
        sd_miso: sdMiso,
        sd_cs: sdCs,
        sd_mount_point: document.getElementById('sd_mount_point').value.trim() || '/sd',
        wdt_enabled: document.getElementById('wdt_enabled').checked,
        log_level: safeInt(document.getElementById('log_level').value, 1)
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

    // Harvest Remote Servers
    const remoteRows = document.querySelectorAll('.remote-row');
    remoteRows.forEach(row => {
        const nameEl = row.querySelector('.remote-name');
        const urlEl = row.querySelector('.remote-url');
        if (!nameEl || !urlEl) return;
        const name = nameEl.value.trim();
        const url = urlEl.value.trim();
        if (name && url) {
            data.remote_servers.push({ name: name, url: url });
        }
    });

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
            clearConfigDirty();
        } else {
            showStatus('Error saving: ' + (result.message || 'Unknown error'), 'error');
        }
    } catch (error) {
        console.error('Error:', error);
        showStatus('Network error while saving.', 'error');
    }
}

async function pollSdStatus() {
    if (isUploading || _dialogOpen || _pollInFlight) {
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

// ---------------------------------------------------------
// BLANK DISK CREATION MODAL
// ---------------------------------------------------------
function showCreateDiskModal() {
    _dialogOpen = true;
    document.getElementById('new-disk-name').value = 'blank_disk.dsk';
    document.getElementById('create-disk-modal').style.display = 'flex';
}

function hideCreateDiskModal() {
    document.getElementById('create-disk-modal').style.display = 'none';
    _dialogOpen = false;
}

async function submitCreateDisk() {
    const nameInput = document.getElementById('new-disk-name').value.trim();
    const sizeInput = document.getElementById('new-disk-size').value;
    const btn = document.getElementById('btn-create-submit');

    if (!nameInput) {
        alert("Please enter a filename.");
        return;
    }

    // UI Loading state
    btn.disabled = true;
    btn.textContent = 'STARTING...';
    btn.style.opacity = '0.7';

    try {
        const response = await fetch('/api/files/create', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filename: nameInput, size: sizeInput })
        });

        if (!response.ok) {
            const data = await response.json();
            alert('Failed to create disk: ' + (data.error || 'Unknown error.'));
            btn.disabled = false;
            btn.textContent = 'CREATE';
            btn.style.opacity = '1';
            return;
        }

        // Poll for progress
        let creationDone = false;
        let pollInFlight = false;
        const pollInterval = setInterval(async () => {
            if (creationDone || pollInFlight) return;
            pollInFlight = true;
            try {
                const statusRes = await fetch('/api/files/create/status');
                const status = await statusRes.json();

                if (status.total > 0) {
                    const pct = (status.written / status.total) * 100;
                    btn.textContent = `CREATING... ${Math.round(pct)}%`;
                }

                if (status.state === 'complete' && !creationDone) {
                    creationDone = true;
                    clearInterval(pollInterval);
                    btn.textContent = 'COMPLETE!';
                    setTimeout(() => {
                        hideCreateDiskModal();
                        refreshFilesTab();
                    }, 1000);
                } else if (status.state === 'error' && !creationDone) {
                    creationDone = true;
                    clearInterval(pollInterval);
                    alert('CREATION FAILED: ' + (status.error || 'Unknown error'));
                    btn.disabled = false;
                    btn.textContent = 'CREATE';
                    btn.style.opacity = '1';
                }
            } catch (e) {
                console.warn('Disk creation status poll error', e);
            } finally {
                pollInFlight = false;
            }
        }, 1000);

    } catch (error) {
        alert('Network error while creating disk: ' + error.message);
        btn.disabled = false;
        btn.textContent = 'CREATE';
        btn.style.opacity = '1';
    }
}

// ---------------------------------------------------------
// REMOTE SERVER MANAGEMENT
// ---------------------------------------------------------

async function fetchRemoteFiles() {
    if (_remoteInFlight) return;  // Prevent concurrent remote socket allocations
    _remoteInFlight = true;
    try {
        const response = await fetch('/api/remote/files');
        if (response.ok) {
            const data = await response.json();
            const flattened = [];
            if (data.servers) {
                data.servers.forEach(srv => {
                    if (srv.files) {
                        srv.files.forEach(filename => {
                            flattened.push({
                                name: filename,
                                server: srv.name,
                                url: srv.url
                            });
                        });
                    }
                });
            }
            _remoteFiles = flattened;
        } else {
            _remoteFiles = [];
        }
    } catch (e) {
        console.warn('Failed to fetch remote files', e);
        _remoteFiles = [];
    } finally {
        _remoteInFlight = false;
    }
}

function renderRemoteServers(servers) {
    const container = document.getElementById('remote-servers-container');
    if (!container) return;
    container.innerHTML = '';

    if (!Array.isArray(servers) || servers.length === 0) {
        container.innerHTML = '<p style="color:var(--coco-dark-green);">NO REMOTE SERVERS CONFIGURED.</p>';
        return;
    }

    servers.forEach(srv => {
        addRemoteServerRow(srv.name || '', srv.url || '');
    });
}

function addRemoteServer() {
    const container = document.getElementById('remote-servers-container');
    if (container.querySelector('p')) container.innerHTML = '';
    addRemoteServerRow('', '');
    markConfigDirty();
}

function addRemoteServerRow(name, url) {
    const container = document.getElementById('remote-servers-container');
    const div = document.createElement('div');
    div.className = 'remote-row';

    div.innerHTML = `
        <div style="flex:2">
            <label>NAME</label>
            <input type="text" class="remote-name" value="${escHtml(name)}" placeholder="DEV SERVER">
        </div>
        <div style="flex:3">
            <label>URL</label>
            <input type="text" class="remote-url" value="${escHtml(url)}" placeholder="http://192.168.1.100:8080">
        </div>
        <div class="remote-status" title="Connection status">⚪</div>
        <div class="remote-actions">
            <button class="btn btn-action btn-test" onclick="testRemoteServer(this)">TEST</button>
            <button class="btn btn-danger btn-delete" onclick="this.closest('.remote-row').remove(); markConfigDirty();">X</button>
        </div>
    `;
    container.appendChild(div);
}

async function testRemoteServer(btn) {
    const row = btn.closest('.remote-row');
    const urlEl = row.querySelector('.remote-url');
    const statusEl = row.querySelector('.remote-status');
    const url = urlEl.value.trim();

    if (!url) {
        statusEl.textContent = '\uD83D\uDD34';
        statusEl.title = 'No URL specified';
        return;
    }

    statusEl.textContent = '\u23F3';
    statusEl.title = 'Testing...';

    try {
        const response = await fetch('/api/remote/test', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url: url })
        });
        const data = await response.json();
        if (data.status === 'ok') {
            const diskCount = data.info?.disk_count || 0;
            statusEl.textContent = '\uD83D\uDFE2';
            statusEl.title = `Connected: ${diskCount} disk(s) found`;
            // Remote connection established, fetch files again to ensure dropdowns are populated
            await fetchRemoteFiles();
            refreshDriveSelects();
        } else {
            statusEl.textContent = '\uD83D\uDD34';
            statusEl.title = data.message || 'Connection failed';
        }
    } catch (e) {
        statusEl.textContent = '\uD83D\uDD34';
        statusEl.title = 'Network error: ' + e;
    }
}

// ---------------------------------------------------------
// CLONE MODAL
// ---------------------------------------------------------

function showCloneModal(serverUrl, diskName, serverName, driveNum) {
    _cloneServerUrl = serverUrl;
    _cloneDiskName = diskName;
    _dialogOpen = true;

    const infoEl = document.getElementById('clone-info');
    infoEl.textContent = `CLONE "${diskName}" FROM ${serverName || serverUrl} TO LOCAL SD CARD`;

    document.getElementById('clone-local-name').value = diskName;

    // Dynamically build drive dropdown showing current assignments
    const sel = document.getElementById('clone-drive-num');
    sel.innerHTML = '<option value="-1">(CLONE ONLY - NO DRIVE ASSIGNMENT)</option>';
    for (let i = 0; i < 4; i++) {
        const opt = document.createElement('option');
        opt.value = i;
        const assigned = _driveAssignments[i];
        const driveLabel = assigned
            ? `DRIVE ${i}: ${assigned.split('/').pop()}`
            : `DRIVE ${i}: (EMPTY)`;
        opt.textContent = driveLabel;
        sel.appendChild(opt);
    }
    sel.value = driveNum != null ? driveNum : -1;

    document.getElementById('clone-progress-container').style.display = 'none';
    document.getElementById('clone-progress-bar').style.width = '0%';
    document.getElementById('clone-status-text').textContent = '';
    document.getElementById('btn-clone-submit').disabled = false;
    document.getElementById('btn-clone-submit').textContent = 'CLONE';
    document.getElementById('btn-clone-cancel').disabled = false;
    document.getElementById('clone-modal').style.display = 'flex';
}

function hideCloneModal() {
    document.getElementById('clone-modal').style.display = 'none';
    _dialogOpen = false;
}

async function submitClone() {
    const localName = document.getElementById('clone-local-name').value.trim();
    const driveNum = parseInt(document.getElementById('clone-drive-num').value);
    const btn = document.getElementById('btn-clone-submit');
    const cancelBtn = document.getElementById('btn-clone-cancel');

    if (!localName) {
        document.getElementById('clone-status-text').textContent = 'PLEASE ENTER A FILENAME';
        return;
    }

    btn.disabled = true;
    btn.textContent = 'CLONING...';
    cancelBtn.disabled = true;
    document.getElementById('clone-progress-container').style.display = 'block';
    document.getElementById('clone-status-text').textContent = 'STARTING CLONE...';

    try {
        const response = await fetch('/api/remote/clone', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                remote_url: _cloneServerUrl,
                disk_name: _cloneDiskName,
                local_path: '/sd/' + localName,
                drive_num: driveNum
            })
        });

        const data = await response.json();
        if (data.error) {
            document.getElementById('clone-status-text').textContent = 'ERROR: ' + data.error;
            btn.disabled = false;
            btn.textContent = 'CLONE';
            cancelBtn.disabled = false;
            return;
        }

        // Poll for progress
        let cloneDone = false;
        let pollInFlight = false;
        const pollInterval = setInterval(async () => {
            if (cloneDone || pollInFlight) return;
            pollInFlight = true;
            try {
                const statusRes = await fetch('/api/remote/clone/status');
                const status = await statusRes.json();

                if (status.total > 0) {
                    const pct = (status.progress / status.total) * 100;
                    document.getElementById('clone-progress-bar').style.width = pct + '%';
                    document.getElementById('clone-status-text').textContent =
                        `${status.state.toUpperCase()}: ${status.progress} / ${status.total} SECTORS`;
                }

                if (status.state === 'complete' && !cloneDone) {
                    cloneDone = true;
                    clearInterval(pollInterval);
                    document.getElementById('clone-progress-bar').style.width = '100%';
                    document.getElementById('clone-status-text').textContent = 'CLONE COMPLETE!';

                    // Final UI refresh sequence
                    setTimeout(async () => {
                        hideCloneModal();

                        // Consolidation: refreshFilesTab already fetches files and remote files.
                        // We also need fresh config for drive assignments, but we can do it 
                        // efficiently by coordinating with refreshFilesTab.
                        await refreshFilesTab();

                        const freshConfig = await fetchConfig();
                        const freshDrives = freshConfig.drives || [null, null, null, null];
                        // refreshDriveSelects already called inside refreshFilesTab indirectly
                        // via the 'files' tab switch or manual call? No, it's called here.
                        // Let's pass the files we just got if we can, or just call it.
                        await refreshDriveSelects();

                        for (let i = 0; i < 4; i++) {
                            const sel = document.getElementById(`drive_${i}`);
                            if (sel) sel.value = freshDrives[i] || '';
                        }
                    }, 1500);
                } else if (status.state === 'error' && !cloneDone) {
                    cloneDone = true;
                    clearInterval(pollInterval);
                    document.getElementById('clone-status-text').textContent = 'ERROR: ' + (status.error || 'Unknown');
                    btn.disabled = false;
                    btn.textContent = 'RETRY';
                    cancelBtn.disabled = false;
                }
            } catch (e) {
                console.warn('Clone status poll error', e);
            } finally {
                pollInFlight = false;
            }
        }, 1000);

    } catch (e) {
        document.getElementById('clone-status-text').textContent = 'NETWORK ERROR: ' + e;
        btn.disabled = false;
        btn.textContent = 'CLONE';
        cancelBtn.disabled = false;
    }
}


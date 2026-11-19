document.addEventListener('DOMContentLoaded', () => {
    // Éléments DOM
    const urlInput = document.getElementById('urlInput');
    const btnClearUrl = document.getElementById('btnClearUrl');
    const btnPaste = document.getElementById('btnPaste');
    const btnInspect = document.getElementById('btnInspect');

    const videoPreview = document.getElementById('videoPreview');
    const previewThumb = document.getElementById('previewThumb');
    const previewTitle = document.getElementById('previewTitle');
    const previewUploader = document.getElementById('previewUploader');
    const previewDuration = document.getElementById('previewDuration');
    const previewMaxRes = document.getElementById('previewMaxRes');

    const formatButtons = document.querySelectorAll('.format-btn');
    const resRow = document.getElementById('resRow');
    const resPills = document.querySelectorAll('.res-pill');

    const btnDownload = document.getElementById('btnDownload');
    const statusDot = document.getElementById('statusDot');
    const statusText = document.getElementById('statusText');
    const progressPct = document.getElementById('progressPct');
    const progressFill = document.getElementById('progressFill');
    const speedText = document.getElementById('speedText');
    const etaText = document.getElementById('etaText');

    const readyCard = document.getElementById('readyCard');
    const readyTitle = document.getElementById('readyTitle');
    const readyDetails = document.getElementById('readyDetails');
    const readyDownloadBtn = document.getElementById('readyDownloadBtn');

    const historyList = document.getElementById('historyList');
    const historyEmpty = document.getElementById('historyEmpty');
    const btnClearHistory = document.getElementById('btnClearHistory');

    // État
    let currentFormat = "MP4";
    let currentResolution = "source";
    let isProcessing = false;
    let ws = null;

    // Charger l'historique local
    loadHistory();

    // ── GESTION URL ──
    urlInput.addEventListener('input', () => {
        btnClearUrl.style.display = urlInput.value ? 'block' : 'none';
    });

    btnClearUrl.addEventListener('click', () => {
        urlInput.value = '';
        btnClearUrl.style.display = 'none';
        videoPreview.style.display = 'none';
        urlInput.focus();
    });

    btnPaste.addEventListener('click', async () => {
        try {
            const text = await navigator.clipboard.readText();
            if (text) {
                urlInput.value = text.trim();
                btnClearUrl.style.display = 'block';
                inspectUrl(text.trim());
            }
        } catch (e) {
            alert("Veuillez autoriser l'accès au presse-papiers ou coller directement avec Ctrl+V.");
        }
    });

    btnInspect.addEventListener('click', () => {
        const val = urlInput.value.trim();
        if (val) inspectUrl(val);
    });

    urlInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            const val = urlInput.value.trim();
            if (val) inspectUrl(val);
        }
    });

    // ── ANALYSE DE L'URL (METADATA) ──
    async function inspectUrl(url) {
        btnInspect.disabled = true;
        btnInspect.innerHTML = `<span>⏳</span> Analyse...`;
        
        try {
            const res = await fetch('/api/info', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url: url })
            });

            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || "Erreur de lecture");
            }

            const data = await res.json();
            previewTitle.textContent = data.title;
            previewUploader.textContent = `👤 ${data.uploader}`;
            previewDuration.textContent = `⏱ ${data.duration_str}`;
            previewMaxRes.textContent = data.max_res;
            previewThumb.src = data.thumbnail;
            videoPreview.style.display = 'flex';

            statusText.textContent = `● Vidéo trouvée : ${data.title.substring(0, 45)}...`;
            statusDot.className = "status-dot ready";
        } catch (err) {
            console.error("Inspect error:", err);
        } finally {
            btnInspect.disabled = false;
            btnInspect.innerHTML = `<span>🔍</span> Analyser`;
        }
    }

    // ── CHOIX DU FORMAT ──
    formatButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            formatButtons.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentFormat = btn.dataset.format;

            // Si MP3, cacher la rangée de résolution (inutile pour de l'audio)
            if (currentFormat === "MP3") {
                resRow.style.display = "none";
            } else {
                resRow.style.display = "flex";
            }
        });
    });

    // ── CHOIX DE LA RÉSOLUTION ──
    resPills.forEach(pill => {
        pill.addEventListener('click', () => {
            resPills.forEach(p => p.classList.remove('active'));
            pill.classList.add('active');
            currentResolution = pill.dataset.res;
        });
    });

    // ── LANCEMENT DU TÉLÉCHARGEMENT ──
    btnDownload.addEventListener('click', () => {
        const url = urlInput.value.trim();
        if (!url) {
            alert("Veuillez coller une URL vidéo.");
            urlInput.focus();
            return;
        }

        if (isProcessing) return;
        startDownload(url);
    });

    function startDownload(url) {
        isProcessing = true;
        btnDownload.disabled = true;
        btnDownload.innerHTML = `<span class="btn-icon">⚡</span> <span class="btn-text">TRAITEMENT EN COURS...</span>`;
        readyCard.style.display = "none";

        // Reset progression
        progressPct.textContent = "0%";
        progressFill.style.width = "0%";
        speedText.textContent = "Vitesse : --";
        etaText.textContent = "Temps restant : --";
        statusDot.className = "status-dot working";
        statusText.textContent = "Connexion au serveur de conversion...";

        // Connexion WebSocket
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/download`;

        ws = new WebSocket(wsUrl);

        ws.onopen = () => {
            statusText.textContent = "Téléchargement en cours...";
            ws.send(JSON.stringify({
                url: url,
                format: currentFormat,
                resolution: currentResolution
            }));
        };

        ws.onmessage = (event) => {
            try {
                const msg = JSON.parse(event.data);

                if (msg.type === "status") {
                    statusText.textContent = msg.message;
                    if (msg.message.includes("Recodage") || msg.message.includes("Finalisation")) {
                        statusDot.className = "status-dot converting";
                    }
                } else if (msg.type === "progress") {
                    const p = Math.min(Math.max(msg.percent, 0), 100);
                    progressPct.textContent = `${p}%`;
                    progressFill.style.width = `${p}%`;
                    speedText.textContent = `Vitesse : ${msg.speed || '--'}`;
                    etaText.textContent = `Temps restant : ${msg.eta || '--'}`;
                } else if (msg.type === "complete") {
                    onDownloadComplete(msg);
                } else if (msg.type === "error") {
                    onDownloadError(msg.message);
                }
            } catch (err) {
                console.error("WS error:", err);
            }
        };

        ws.onerror = (err) => {
            console.error("WebSocket error:", err);
            onDownloadError("Erreur de connexion au serveur.");
        };

        ws.onclose = () => {
            if (isProcessing) {
                resetDownloadButtons();
            }
        };
    }

    function onDownloadComplete(result) {
        isProcessing = false;
        resetDownloadButtons();

        statusDot.className = "status-dot ready";
        statusText.textContent = "✅ Traitement terminé ! Téléchargement prêt.";
        progressPct.textContent = "100%";
        progressFill.style.width = "100%";
        speedText.textContent = "Vitesse : Terminé";
        etaText.textContent = "Temps restant : 00:00";

        // Afficher la carte de téléchargement
        readyTitle.textContent = result.title;
        readyDetails.textContent = `${currentFormat} • ${currentResolution === 'source' ? 'HD/Max' : currentResolution} • ${result.size}`;
        readyDownloadBtn.href = result.download_url;
        readyDownloadBtn.download = result.filename;
        readyCard.style.display = "flex";

        // Déclencher le téléchargement automatiquement dans le navigateur
        const autoLink = document.createElement('a');
        autoLink.href = result.download_url;
        autoLink.download = result.filename;
        document.body.appendChild(autoLink);
        autoLink.click();
        document.body.removeChild(autoLink);

        // Ajouter à l'historique
        addToHistory({
            title: result.title,
            format: currentFormat,
            size: result.size,
            url: result.download_url,
            filename: result.filename,
            time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        });
    }

    function onDownloadError(errorMsg) {
        isProcessing = false;
        resetDownloadButtons();

        statusDot.className = "status-dot error";
        statusText.textContent = `❌ Erreur : ${errorMsg}`;
        progressFill.style.width = "0%";
        progressPct.textContent = "0%";
        alert(`Erreur lors du téléchargement :\n${errorMsg}`);
    }

    function resetDownloadButtons() {
        btnDownload.disabled = false;
        btnDownload.innerHTML = `<span class="btn-icon">⚡</span> <span class="btn-text">TÉLÉCHARGER & RECODER POUR REGIE/PREMIERE</span>`;
    }

    // ── HISTORIQUE LOCAL ──
    function loadHistory() {
        try {
            const raw = localStorage.getItem('viddrop_web_history');
            const items = raw ? JSON.parse(raw) : [];
            renderHistory(items);
        } catch {
            renderHistory([]);
        }
    }

    function addToHistory(item) {
        try {
            const raw = localStorage.getItem('viddrop_web_history');
            const items = raw ? JSON.parse(raw) : [];
            items.unshift(item);
            if (items.length > 20) items.pop();
            localStorage.setItem('viddrop_web_history', JSON.stringify(items));
            renderHistory(items);
        } catch {}
    }

    function renderHistory(items) {
        historyList.innerHTML = '';
        if (!items || items.length === 0) {
            historyList.appendChild(historyEmpty);
            historyEmpty.style.display = 'block';
            return;
        }

        historyEmpty.style.display = 'none';
        items.forEach((item, idx) => {
            const div = document.createElement('div');
            div.className = 'history-item';
            div.innerHTML = `
                <div class="history-info">
                    <div class="history-title" title="${item.title}">${item.title}</div>
                    <div class="history-time">✅ ${item.time} • ${item.format} • ${item.size}</div>
                </div>
                <div class="history-actions">
                    <a href="${item.url}" class="btn-icon-sm" download="${item.filename}" title="Télécharger">💾</a>
                    <button class="btn-icon-sm btn-del" data-idx="${idx}" title="Supprimer">✕</button>
                </div>
            `;
            historyList.appendChild(div);
        });

        document.querySelectorAll('.btn-del').forEach(b => {
            b.addEventListener('click', (e) => {
                const idx = parseInt(e.target.dataset.idx);
                deleteHistoryItem(idx);
            });
        });
    }

    function deleteHistoryItem(idx) {
        try {
            const raw = localStorage.getItem('viddrop_web_history');
            const items = raw ? JSON.parse(raw) : [];
            items.splice(idx, 1);
            localStorage.setItem('viddrop_web_history', JSON.stringify(items));
            renderHistory(items);
        } catch {}
    }

    btnClearHistory.addEventListener('click', () => {
        localStorage.removeItem('viddrop_web_history');
        renderHistory([]);
    });
});

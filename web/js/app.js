class NovaVoiceApp {
    constructor() {
        this.ws = null;
        this.mediaStream = null;
        this.audioContext = null;
        this.processorNode = null;
        this.isRecording = false;
        this.sessionStart = null;
        this.timerInterval = null;
        this.playbackQueue = [];
        this.isPlaying = false;
        this.agentName = 'Nova';

        this.micButton = document.getElementById('micButton');
        this.micIcon = document.querySelector('.mic-icon');
        this.stopIcon = document.querySelector('.stop-icon');
        this.statusPill = document.getElementById('statusPill');
        this.statusText = document.querySelector('.status-text');
        this.voiceVisualizer = document.getElementById('voiceVisualizer');
        this.voiceInstruction = document.getElementById('voiceInstruction');
        this.waveformBar = document.getElementById('waveformBar');
        this.eventsLog = document.getElementById('eventsLog');
        this.sessionTimer = document.getElementById('sessionTimer');
        this.waveformCanvas = document.getElementById('waveformCanvas');
        this.canvasCtx = this.waveformCanvas.getContext('2d');

        this._turnIndicator = document.getElementById('turnIndicator');
        this._turnDot       = document.getElementById('turnDot');
        this._turnText      = document.getElementById('turnText');
        this._aiSpeaking    = false;

        this.init();
        this._loadPromptInfo();
    }

    init() {
        this.micButton.addEventListener('click', () => this.toggleRecording());
        document.getElementById('btnClearLog').addEventListener('click', () => this.clearLog());

        this.drawIdleWaveform();
    }

    async toggleRecording() {
        if (this.isRecording) {
            this.stopRecording();
        } else {
            await this.startRecording();
        }
    }

    async startRecording() {
        try {
            this.mediaStream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    sampleRate: 16000,
                    channelCount: 1,
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true
                }
            });

            this.audioContext = new AudioContext({ sampleRate: 16000 });
            const source = this.audioContext.createMediaStreamSource(this.mediaStream);

            this.processorNode = this.audioContext.createScriptProcessor(4096, 1, 1);
            this.processorNode.onaudioprocess = (event) => {
                if (!this.isRecording || !this.ws || this.ws.readyState !== WebSocket.OPEN) return;

                const inputData = event.inputBuffer.getChannelData(0);
                const pcm16 = new Int16Array(inputData.length);
                for (let i = 0; i < inputData.length; i++) {
                    const s = Math.max(-1, Math.min(1, inputData[i]));
                    pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
                }
                this.ws.send(pcm16.buffer);
            };

            source.connect(this.processorNode);
            this.processorNode.connect(this.audioContext.destination);

            this.connectWebSocket();

        } catch (err) {
            this.logEvent('error', `Error al acceder al micrófono: ${err.message}`);
        }
    }

    connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/voice`;

        this.ws = new WebSocket(wsUrl);
        this.ws.binaryType = 'arraybuffer';

        this.ws.onopen = () => {
            this.isRecording = true;
            this.sessionStart = Date.now();
            this.updateUI('recording');
            this.startTimer();
            this.startWaveformAnimation();
            this.logEvent('system', 'Conectado al Asistente Virtual. Habla ahora...');
        };

        this.ws.onmessage = (event) => {
            if (event.data instanceof ArrayBuffer) {
                this.playbackQueue.push(event.data);
                if (!this._aiSpeaking) this._setTurn('ai');
                if (!this.isPlaying) this.playNextChunk();
            }
        };

        this.ws.onclose = () => {
            if (this.isRecording) {
                this.stopRecording();
            }
            this.logEvent('system', 'Conexión cerrada');
        };

        this.ws.onerror = (err) => {
            this.logEvent('error', 'Error de conexión WebSocket');
        };
    }

    async playNextChunk() {
        if (this.playbackQueue.length === 0) {
            this.isPlaying = false;
            if (this._aiSpeaking) this._setTurn('user');
            return;
        }

        this.isPlaying = true;
        const audioData = this.playbackQueue.shift();

        try {
            if (!this.audioContext || this.audioContext.state === 'closed') return;

            const int16Array = new Int16Array(audioData);
            const float32Array = new Float32Array(int16Array.length);
            for (let i = 0; i < int16Array.length; i++) {
                float32Array[i] = int16Array[i] / 32768.0;
            }

            const audioBuffer = this.audioContext.createBuffer(1, float32Array.length, 16000);
            audioBuffer.getChannelData(0).set(float32Array);

            const sourceNode = this.audioContext.createBufferSource();
            sourceNode.buffer = audioBuffer;
            sourceNode.connect(this.audioContext.destination);
            sourceNode.onended = () => this.playNextChunk();
            sourceNode.start();

        } catch (err) {
            this.isPlaying = false;
            this.playNextChunk();
        }
    }

    _setTurn(who) {
        if (!this._turnIndicator) return;
        this._aiSpeaking = (who === 'ai');
        this._turnIndicator.style.display = 'flex';
        if (who === 'ai') {
            this._turnIndicator.style.background = 'rgba(79,142,247,.08)';
            this._turnIndicator.style.borderColor = 'rgba(79,142,247,.3)';
            this._turnIndicator.style.color = '#4f8ef7';
            this._turnDot.style.background = '#4f8ef7';
            this._turnDot.style.boxShadow = '0 0 8px #4f8ef7';
            this._turnText.textContent = `${this.agentName} está hablando…`;
            this.logEvent('ai', `▶ ${this.agentName} está hablando`);
        } else {
            this._turnIndicator.style.background = 'rgba(52,211,153,.08)';
            this._turnIndicator.style.borderColor = 'rgba(52,211,153,.35)';
            this._turnIndicator.style.color = '#34d399';
            this._turnDot.style.background = '#34d399';
            this._turnDot.style.boxShadow = '0 0 8px #34d399';
            this._turnText.textContent = '🎤 Tu turno — habla ahora';
            this.logEvent('system', '🎤 Tu turno');
        }
    }

    async _loadPromptInfo() {
        try {
            const res  = await fetch('/api/admin/prompt-config/active');
            const data = await res.json();
            const card   = document.getElementById('promptInfoCard');
            const pill   = document.getElementById('promptModePill');
            const snip   = document.getElementById('promptSnippet');
            if (!card) return;
            card.style.display = 'block';
            const cfg = await fetch('/api/admin/prompt-config').then(r => r.json()).catch(() => ({}));
            
            let mode = '📂 Archivos del sistema';
            this.agentName = 'Nova';
            
            if (data.config_exists) {
                if (cfg.mode === 'agent') {
                    mode = `🤖 Agente: ${cfg.profile_name || 'Preconfigurado'}`;
                } else if (cfg.mode === 'builder') {
                    mode = '🎨 Constructor Visual';
                } else if (cfg.mode === 'raw') {
                    mode = '📝 Texto / JSON';
                }
                
                if (cfg.builder?.identity?.name) {
                    this.agentName = cfg.builder.identity.name;
                }
            }
            
            pill.textContent = mode;
            snip.textContent = data.prompt_preview || 'Sin contenido';
            
            if (this.voiceInstruction && !this.isRecording) {
                this.voiceInstruction.textContent = `Presiona el micrófono para hablar con ${this.agentName}`;
            }
        } catch {}
    }

    stopRecording() {
        this.isRecording = false;

        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ type: 'end' }));
            this.ws.close();
        }

        if (this.processorNode) {
            this.processorNode.disconnect();
            this.processorNode = null;
        }

        if (this.mediaStream) {
            this.mediaStream.getTracks().forEach(track => track.stop());
            this.mediaStream = null;
        }

        if (this.audioContext && this.audioContext.state !== 'closed') {
            this.audioContext.close();
            this.audioContext = null;
        }

        this.stopTimer();
        this.updateUI('idle');
        this.playbackQueue = [];
        this.isPlaying = false;
        this.logEvent('system', 'Sesión finalizada');
    }

    updateUI(state) {
        const pill = this.statusPill;
        pill.classList.remove('connected', 'active');

        switch (state) {
            case 'recording':
                pill.classList.add('active');
                this.statusText.textContent = 'En llamada';
                this.micButton.classList.add('recording');
                this.micIcon.classList.add('hidden');
                this.stopIcon.classList.remove('hidden');
                this.voiceVisualizer.classList.add('active');
                this.waveformBar.classList.add('active');
                this.voiceInstruction.textContent = `Escuchando... Habla con ${this.agentName}`;
                break;

            case 'idle':
            default:
                this.statusText.textContent = 'Desconectado';
                this.micButton.classList.remove('recording');
                this.micIcon.classList.remove('hidden');
                this.stopIcon.classList.add('hidden');
                this.voiceVisualizer.classList.remove('active');
                this.waveformBar.classList.remove('active');
                this.voiceInstruction.textContent = `Presiona el micrófono para hablar con ${this.agentName}`;
                break;
        }
    }

    startTimer() {
        this.timerInterval = setInterval(() => {
            const elapsed = Math.floor((Date.now() - this.sessionStart) / 1000);
            const mins = String(Math.floor(elapsed / 60)).padStart(2, '0');
            const secs = String(elapsed % 60).padStart(2, '0');
            this.sessionTimer.textContent = `${mins}:${secs}`;
        }, 1000);
    }

    stopTimer() {
        if (this.timerInterval) {
            clearInterval(this.timerInterval);
            this.timerInterval = null;
        }
        this.sessionTimer.textContent = '00:00';
    }

    startWaveformAnimation() {
        const bars = document.querySelectorAll('.wave-bar');
        const animate = () => {
            if (!this.isRecording) return;
            bars.forEach(bar => {
                const height = Math.random() * 36 + 4;
                bar.style.height = `${height}px`;
            });
            requestAnimationFrame(animate);
        };
        animate();
        this.animateCanvasWaveform();
    }

    animateCanvasWaveform() {
        const canvas = this.waveformCanvas;
        const ctx = this.canvasCtx;
        const centerX = canvas.width / 2;
        const centerY = canvas.height / 2;
        let phase = 0;

        const draw = () => {
            if (!this.isRecording) {
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                return;
            }

            ctx.clearRect(0, 0, canvas.width, canvas.height);
            phase += 0.03;

            for (let ring = 0; ring < 3; ring++) {
                const baseRadius = 60 + ring * 22;
                ctx.beginPath();
                for (let angle = 0; angle <= Math.PI * 2; angle += 0.02) {
                    const noise = Math.sin(angle * 4 + phase + ring) * 3 +
                                  Math.sin(angle * 7 - phase * 1.3) * 2;
                    const radius = baseRadius + noise;
                    const x = centerX + Math.cos(angle) * radius;
                    const y = centerY + Math.sin(angle) * radius;
                    if (angle === 0) ctx.moveTo(x, y);
                    else ctx.lineTo(x, y);
                }
                ctx.closePath();
                const alpha = 0.15 - ring * 0.03;
                const colors = ['129, 140, 248', '192, 132, 252', '103, 232, 249'];
                ctx.strokeStyle = `rgba(${colors[ring]}, ${alpha})`;
                ctx.lineWidth = 1.5;
                ctx.stroke();
            }

            requestAnimationFrame(draw);
        };
        draw();
    }

    drawIdleWaveform() {
        const canvas = this.waveformCanvas;
        const ctx = this.canvasCtx;
        ctx.clearRect(0, 0, canvas.width, canvas.height);
    }

    logEvent(type, message) {
        const now = new Date();
        const time = now.toLocaleTimeString('es-MX', { hour12: false });

        const badgeMap = {
            system: ['SISTEMA', 'badge-system'],
            audio: ['AUDIO', 'badge-audio'],
            ai: ['IA', 'badge-ai'],
            action: ['ACCIÓN', 'badge-action'],
            error: ['ERROR', 'badge-error'],
            function: ['FUNCIÓN', 'badge-function']
        };

        const [label, badgeClass] = badgeMap[type] || badgeMap.system;

        const item = document.createElement('div');
        item.className = `event-item event-${type}`;
        item.innerHTML = `
            <span class="event-time">${time}</span>
            <span class="event-badge ${badgeClass}">${label}</span>
            <span class="event-text">${message}</span>
        `;

        this.eventsLog.appendChild(item);
        this.eventsLog.scrollTop = this.eventsLog.scrollHeight;

        while (this.eventsLog.children.length > 100) {
            this.eventsLog.removeChild(this.eventsLog.firstChild);
        }
    }

    clearLog() {
        this.eventsLog.innerHTML = '';
        this.logEvent('system', 'Log limpiado');
    }
}

document.addEventListener('DOMContentLoaded', () => {
    window.novaApp = new NovaVoiceApp();
});

class RemoteDesktop {
    constructor() {
        this.socket = null;
        this.flvPlayer = null;
        this.videoElement = document.getElementById('video-player');
        this.touchLayer = document.getElementById('touch-layer');
        
        this.statusIndicator = document.getElementById('status-indicator');
        this.statusText = document.getElementById('status-text');
        this.latencyText = document.getElementById('latency-text');
        
        this.touchState = {
            active: false,
            startX: 0,
            startY: 0,
            lastX: 0,
            lastY: 0,
            lastCenterX: 0,
            lastCenterY: 0,
            startTime: 0,
            isLongPress: false,
            isDragging: false,
            moveThreshold: 10,
            longPressDelay: 500,
            longPressTimer: null,
            fingers: 0
        };
        
        this.activeModifiers = new Set();
        this.desktopWidth = 1920;
        this.desktopHeight = 1080;
        
        this.init();
    }
    
    init() {
        this.setupSocket();
        this.setupTouchHandlers();
        this.setupKeyboard();
        this.setupTextInput();
        this.requestStatus();
    }
    
    setStatus(status, text) {
        this.statusIndicator.className = status;
        this.statusText.textContent = text;
    }
    
    _safeEmit(event, data) {
        if (this.socket && this.socket.connected) {
            this.socket.emit(event, data);
        }
    }
    
    setupSocket() {
        this.setStatus('connecting', '连接中...');
        
        this.socket = io({
            transports: ['websocket', 'polling']
        });
        
        this.socket.on('connect', () => {
            this.setStatus('connected', '已连接');
            this.requestStatus();
        });
        
        this.socket.on('disconnect', () => {
            this.setStatus('disconnected', '已断开');
        });
        
        this.socket.on('connect_error', () => {
            this.setStatus('disconnected', '连接失败');
        });
        
        this.socket.on('paste:result', (data) => {
            if (data.success) {
                document.getElementById('text-input').value = '';
            }
        });
    }
    
    async requestStatus() {
        try {
            const res = await fetch('/api/status');
            const data = await res.json();
            if (data.streaming && data.stream_url) {
                this.initPlayer(data.stream_url);
            }
        } catch (e) {
            console.error('Failed to get status:', e);
        }
    }
    
    initPlayer(streamUrl) {
        if (this.flvPlayer) {
            try {
                this.flvPlayer.destroy();
            } catch (e) {}
            this.flvPlayer = null;
        }
        
        if (flvjs.isSupported()) {
            this.flvPlayer = flvjs.createPlayer({
                type: 'flv',
                url: streamUrl,
                isLive: true,
                hasAudio: true,
                hasVideo: true
            }, {
                enableStashBuffer: false,
                stashInitialSize: 128,
                liveBufferLength: 0,
                liveSyncDurationCount: 1,
                liveMaxLatencyDurationCount: 3,
                lazyLoad: false,
                lazyLoadMaxDuration: 0,
                deferLoadAfterSourceOpen: false,
                autoCleanupSourceBuffer: true,
                autoCleanupMaxBackwardDuration: 1,
                autoCleanupMinBackwardDuration: 0.5
            });
            
            this.flvPlayer.attachMediaElement(this.videoElement);
            this.flvPlayer.load();
            this.videoElement.play().catch(e => console.log('Play error:', e));
            
            this.flvPlayer.on(flvjs.Events.STATISTICS_INFO, (stats) => {
                if (stats.decodedFrames && stats.decodedFrames > 0) {
                    const buf = this.videoElement.buffered;
                    if (buf.length > 0) {
                        const latency = buf.end(buf.length - 1) - this.videoElement.currentTime;
                        this.latencyText.textContent = `${(latency * 1000).toFixed(0)}ms`;
                    }
                }
            });

            this.flvPlayer.on(flvjs.Events.ERROR, (errorType, errorDetail, errorInfo) => {
                console.error('FLV error:', errorType, errorDetail, errorInfo);
            });
        }
    }
    
    getVideoRect() {
        const rect = this.videoElement.getBoundingClientRect();
        const videoW = this.videoElement.videoWidth || 1920;
        const videoH = this.videoElement.videoHeight || 1080;
        const videoRatio = videoW / videoH;
        const containerRatio = rect.width / rect.height;
        
        let displayWidth, displayHeight, offsetX, offsetY;
        
        if (containerRatio > videoRatio) {
            displayHeight = rect.height;
            displayWidth = displayHeight * videoRatio;
            offsetX = (rect.width - displayWidth) / 2;
            offsetY = 0;
        } else {
            displayWidth = rect.width;
            displayHeight = displayWidth / videoRatio;
            offsetX = 0;
            offsetY = (rect.height - displayHeight) / 2;
        }
        
        return {
            left: rect.left + offsetX,
            top: rect.top + offsetY,
            width: displayWidth,
            height: displayHeight
        };
    }
    
    _getTouchCenter(touches) {
        if (touches.length === 1) {
            return { x: touches[0].clientX, y: touches[0].clientY };
        }
        let sumX = 0, sumY = 0;
        for (let i = 0; i < touches.length; i++) {
            sumX += touches[i].clientX;
            sumY += touches[i].clientY;
        }
        return {
            x: sumX / touches.length,
            y: sumY / touches.length
        };
    }
    
    screenToDesktop(clientX, clientY) {
        const rect = this.getVideoRect();
        const x = Math.max(0, Math.min(rect.width, clientX - rect.left));
        const y = Math.max(0, Math.min(rect.height, clientY - rect.top));
        const desktopX = (x / rect.width) * this.desktopWidth;
        const desktopY = (y / rect.height) * this.desktopHeight;
        return { x: Math.round(desktopX), y: Math.round(desktopY) };
    }
    
    setupTouchHandlers() {
        const layer = this.touchLayer;
        
        layer.addEventListener('touchstart', (e) => {
            e.preventDefault();
            e.stopPropagation();
            
            this.touchState.fingers = e.touches.length;
            
            if (e.touches.length === 1) {
                const touch = e.touches[0];
                this.touchState.active = true;
                this.touchState.startX = touch.clientX;
                this.touchState.startY = touch.clientY;
                this.touchState.lastX = touch.clientX;
                this.touchState.lastY = touch.clientY;
                this.touchState.startTime = Date.now();
                this.touchState.isLongPress = false;
                this.touchState.isDragging = false;
                
                this.touchState.longPressTimer = setTimeout(() => {
                    this.touchState.isLongPress = true;
                    this.touchState.isDragging = true;
                    this._safeEmit('mouse:right:down');
                }, this.touchState.longPressDelay);
                
            } else if (e.touches.length === 2) {
                const center = this._getTouchCenter(e.touches);
                this.touchState.lastCenterX = center.x;
                this.touchState.lastCenterY = center.y;
                if (this.touchState.longPressTimer) {
                    clearTimeout(this.touchState.longPressTimer);
                    this.touchState.longPressTimer = null;
                }
                if (this.touchState.isDragging && !this.touchState.isLongPress) {
                    this._safeEmit('mouse:left:up');
                    this.touchState.isDragging = false;
                }
            }
        }, { passive: false });
        
        layer.addEventListener('touchmove', (e) => {
            e.preventDefault();
            e.stopPropagation();
            
            if (e.touches.length === 1 && this.touchState.active) {
                const touch = e.touches[0];
                const currentX = touch.clientX;
                const currentY = touch.clientY;
                
                const dx = currentX - this.touchState.startX;
                const dy = currentY - this.touchState.startY;
                
                if (Math.abs(dx) > this.touchState.moveThreshold || 
                    Math.abs(dy) > this.touchState.moveThreshold) {
                    if (this.touchState.longPressTimer) {
                        clearTimeout(this.touchState.longPressTimer);
                        this.touchState.longPressTimer = null;
                    }
                    
                    if (!this.touchState.isDragging && !this.touchState.isLongPress) {
                        this.touchState.isDragging = true;
                        this._safeEmit('mouse:left:down');
                    }
                    
                    const moveDx = currentX - this.touchState.lastX;
                    const moveDy = currentY - this.touchState.lastY;
                    this._safeEmit('mouse:move:rel', {
                        dx: moveDx,
                        dy: moveDy
                    });
                }
                
                this.touchState.lastX = currentX;
                this.touchState.lastY = currentY;
                
            } else if (e.touches.length === 2) {
                const center = this._getTouchCenter(e.touches);
                const moveDy = center.y - this.touchState.lastCenterY;
                const moveDx = center.x - this.touchState.lastCenterX;
                
                if (Math.abs(moveDy) > 2 || Math.abs(moveDx) > 2) {
                    this._safeEmit('mouse:wheel', {
                        dx: Math.round(-moveDx * 2),
                        dy: Math.round(-moveDy * 4)
                    });
                    this.touchState.lastCenterX = center.x;
                    this.touchState.lastCenterY = center.y;
                }
            }
        }, { passive: false });
        
        layer.addEventListener('touchend', (e) => {
            e.preventDefault();
            e.stopPropagation();
            
            if (this.touchState.longPressTimer) {
                clearTimeout(this.touchState.longPressTimer);
                this.touchState.longPressTimer = null;
            }
            
            if (e.touches.length === 0) {
                if (this.touchState.isLongPress) {
                    this._safeEmit('mouse:right:up');
                } else if (this.touchState.isDragging) {
                    this._safeEmit('mouse:left:up');
                } else if (this.touchState.active) {
                    const pos = this.screenToDesktop(this.touchState.startX, this.touchState.startY);
                    this._safeEmit('mouse:move:abs', pos);
                    this._safeEmit('mouse:left:click');
                }
                
                this.touchState.active = false;
                this.touchState.isLongPress = false;
                this.touchState.isDragging = false;
                this.touchState.fingers = 0;
            } else if (e.touches.length === 1) {
                this.touchState.fingers = 1;
                const touch = e.touches[0];
                this.touchState.lastX = touch.clientX;
                this.touchState.lastY = touch.clientY;
            }
        }, { passive: false });
        
        layer.addEventListener('touchcancel', (e) => {
            e.preventDefault();
            if (this.touchState.longPressTimer) {
                clearTimeout(this.touchState.longPressTimer);
                this.touchState.longPressTimer = null;
            }
            if (this.touchState.isLongPress) {
                this._safeEmit('mouse:right:up');
            } else if (this.touchState.isDragging) {
                this._safeEmit('mouse:left:up');
            }
            this.touchState.active = false;
            this.touchState.isLongPress = false;
            this.touchState.isDragging = false;
            this.touchState.fingers = 0;
        }, { passive: false });
        
        layer.addEventListener('contextmenu', (e) => e.preventDefault());
    }
    
    setupKeyboard() {
        const toggleBtn = document.getElementById('keyboard-toggle');
        const keyboard = document.getElementById('virtual-keyboard');
        const closeBtn = document.getElementById('keyboard-close');
        
        toggleBtn.addEventListener('click', () => {
            keyboard.classList.toggle('collapsed');
        });
        
        closeBtn.addEventListener('click', () => {
            keyboard.classList.add('collapsed');
        });
        
        document.querySelectorAll('.modifier-key').forEach(btn => {
            btn.addEventListener('click', () => {
                const key = btn.dataset.key;
                if (this.activeModifiers.has(key)) {
                    this.activeModifiers.delete(key);
                    btn.classList.remove('active');
                    this._safeEmit('key:up', { key });
                } else {
                    this.activeModifiers.add(key);
                    btn.classList.add('active');
                    this._safeEmit('key:down', { key });
                }
            });
        });
        
        document.querySelectorAll('.func-key, .arrow-key').forEach(btn => {
            btn.addEventListener('click', () => {
                const key = btn.dataset.key;
                this.sendKeyWithModifiers(key);
            });
        });
        
        document.querySelectorAll('.shortcut-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const keys = btn.dataset.keys.split(',');
                this._safeEmit('key:combination', { keys });
            });
        });
    }
    
    sendKeyWithModifiers(key) {
        if (this.activeModifiers.size > 0) {
            const keys = [...this.activeModifiers, key];
            this._safeEmit('key:combination', { keys });
            this.clearModifiers();
        } else {
            this._safeEmit('key:press', { key });
        }
    }
    
    clearModifiers() {
        document.querySelectorAll('.modifier-key').forEach(btn => {
            btn.classList.remove('active');
        });
        this.activeModifiers.clear();
    }
    
    setupTextInput() {
        const textInput = document.getElementById('text-input');
        const sendBtn = document.getElementById('send-text');
        
        const sendText = () => {
            const text = textInput.value.trim();
            if (text) {
                this._safeEmit('paste:text', { text });
            }
        };
        
        sendBtn.addEventListener('click', sendText);
        
        textInput.addEventListener('input', (e) => {
            const text = e.target.value;
            if (text.length > 0 && (text.charCodeAt(text.length - 1) > 127 || text.length > 10)) {
                this._safeEmit('paste:text', { text });
                e.target.value = '';
            }
        });
        
        textInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendText();
            }
        });
    }
}

document.addEventListener('DOMContentLoaded', () => {
    window.remoteDesktop = new RemoteDesktop();
});

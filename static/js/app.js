class RemoteDesktop {
    constructor() {
        this.socket = null;
        this.flvPlayer = null;
        this.videoElement = document.getElementById('video-player');
        this.touchLayer = document.getElementById('touch-layer');
        
        this.statusIndicator = document.getElementById('status-indicator');
        this.statusText = document.getElementById('status-text');
        this.latencyText = document.getElementById('latency-text');
        
        this.desktopWidth = 1920;
        this.desktopHeight = 1080;
        
        this.touchState = {
            active: false,
            startX: 0,
            startY: 0,
            lastX: 0,
            lastY: 0,
            lastCenterX: 0,
            lastCenterY: 0,
            lastPinchDist: 0,
            startTime: 0,
            isLongPress: false,
            isDragging: false,
            isPinching: false,
            moveThreshold: 10,
            longPressDelay: 500,
            longPressTimer: null,
            fingers: 0
        };
        
        this.viewState = {
            scale: 1.0,
            minScale: 0.5,
            maxScale: 3.0,
            offsetX: 0,
            offsetY: 0,
            baseWidth: 0,
            baseHeight: 0
        };
        
        this.activeModifiers = new Set();
        this.retryCount = 0;
        this.maxRetries = 5;
        
        this.init();
    }
    
    init() {
        this.setupSocket();
        this.setupTouchHandlers();
        this.setupKeyboard();
        this.setupTextInput();
        this.setupDraggableButton();
        this.setupVideoEvents();
        this.requestStatus();
    }
    
    setStatus(status, text) {
        try {
            this.statusIndicator.className = status;
            this.statusText.textContent = text;
        } catch (e) {}
    }
    
    _safeEmit(event, data) {
        try {
            if (this.socket && this.socket.connected) {
                this.socket.emit(event, data);
            }
        } catch (e) {
            console.warn('Socket emit error:', e);
        }
    }
    
    setupSocket() {
        this.setStatus('connecting', '连接中...');
        
        try {
            this.socket = io({
                transports: ['websocket', 'polling']
            });
        } catch (e) {
            console.error('Socket init error:', e);
            this.setStatus('disconnected', '初始化失败');
            return;
        }
        
        this.socket.on('connect', () => {
            this.setStatus('connected', '已连接');
            this.retryCount = 0;
            this.requestStatus();
        });
        
        this.socket.on('disconnect', () => {
            this.setStatus('disconnected', '已断开');
        });
        
        this.socket.on('connect_error', () => {
            this.setStatus('disconnected', '连接失败');
        });
        
        this.socket.on('paste:result', (data) => {
            try {
                if (data.success) {
                    document.getElementById('text-input').value = '';
                }
            } catch (e) {}
        });
    }
    
    async requestStatus() {
        try {
            const res = await fetch('/api/status');
            const data = await res.json();
            
            if (data.desktop_width && data.desktop_height) {
                this.desktopWidth = data.desktop_width;
                this.desktopHeight = data.desktop_height;
                console.log('Desktop resolution:', this.desktopWidth, 'x', this.desktopHeight);
            }
            
            if (data.streaming && data.stream_url) {
                this.initPlayer(data.stream_url);
            }
        } catch (e) {
            console.error('Failed to get status:', e);
        }
    }
    
    setupVideoEvents() {
        this.videoElement.addEventListener('loadedmetadata', () => {
            console.log('Video loaded:', this.videoElement.videoWidth, 'x', this.videoElement.videoHeight);
            this.resetView();
        });
        
        this.videoElement.addEventListener('play', () => {
            console.log('Video playing');
        });
        
        this.videoElement.addEventListener('error', (e) => {
            console.error('Video error:', e);
        });
    }
    
    initPlayer(streamUrl) {
        if (this.flvPlayer) {
            try {
                this.flvPlayer.destroy();
            } catch (e) {}
            this.flvPlayer = null;
        }
        
        if (typeof flvjs === 'undefined' || !flvjs.isSupported()) {
            console.error('flv.js not supported');
            return;
        }
        
        console.log('Initializing player with URL:', streamUrl);
        
        try {
            this.flvPlayer = flvjs.createPlayer({
                type: 'flv',
                url: streamUrl,
                isLive: true,
                hasAudio: true,
                hasVideo: true,
                cors: true
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
                autoCleanupMinBackwardDuration: 0.5,
                fixAudioTimestampGap: false
            });
            
            this.flvPlayer.attachMediaElement(this.videoElement);
            this.flvPlayer.load();
            
            this.flvPlayer.on(flvjs.Events.SOURCE_SETUP, () => {
                console.log('Source setup, attempting play...');
                this.videoElement.play().then(() => {
                    console.log('Playback started');
                }).catch(e => {
                    console.warn('Autoplay blocked, waiting for user interaction:', e);
                    const startPlay = () => {
                        this.videoElement.play().catch(() => {});
                        document.removeEventListener('touchstart', startPlay);
                        document.removeEventListener('click', startPlay);
                    };
                    document.addEventListener('touchstart', startPlay, { once: true });
                    document.addEventListener('click', startPlay, { once: true });
                });
            });
            
            this.flvPlayer.on(flvjs.Events.STATISTICS_INFO, (stats) => {
                try {
                    if (stats.decodedFrames && stats.decodedFrames > 0) {
                        const buf = this.videoElement.buffered;
                        if (buf.length > 0) {
                            const latency = buf.end(buf.length - 1) - this.videoElement.currentTime;
                            this.latencyText.textContent = `${(latency * 1000).toFixed(0)}ms`;
                        }
                    }
                } catch (e) {}
            });
            
            this.flvPlayer.on(flvjs.Events.ERROR, (errorType, errorDetail, errorInfo) => {
                console.error('FLV error:', errorType, errorDetail, errorInfo);
                if (this.retryCount < this.maxRetries) {
                    this.retryCount++;
                    console.log(`Retrying... (${this.retryCount}/${this.maxRetries})`);
                    setTimeout(() => {
                        this.initPlayer(streamUrl);
                    }, 2000 * this.retryCount);
                }
            });
            
        } catch (e) {
            console.error('Player init error:', e);
        }
    }
    
    resetView() {
        this.viewState.scale = 1.0;
        this.viewState.offsetX = 0;
        this.viewState.offsetY = 0;
        this.applyViewTransform();
    }
    
    applyViewTransform() {
        const { scale, offsetX, offsetY } = this.viewState;
        this.videoElement.style.transform = `translate(${offsetX}px, ${offsetY}px) scale(${scale})`;
        this.videoElement.style.transformOrigin = 'center center';
    }
    
    _getDistance(touches) {
        const dx = touches[0].clientX - touches[1].clientX;
        const dy = touches[0].clientY - touches[1].clientY;
        return Math.sqrt(dx * dx + dy * dy);
    }
    
    _getTouchCenter(touches) {
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
    
    getVideoRect() {
        try {
            const rect = this.touchLayer.getBoundingClientRect();
            const videoW = this.videoElement.videoWidth || this.desktopWidth || 1920;
            const videoH = this.videoElement.videoHeight || this.desktopHeight || 1080;
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
        } catch (e) {
            return { left: 0, top: 0, width: 1, height: 1 };
        }
    }
    
    screenToDesktop(clientX, clientY) {
        try {
            const rect = this.getVideoRect();
            const { scale, offsetX, offsetY } = this.viewState;
            
            const centerX = rect.left + rect.width / 2;
            const centerY = rect.top + rect.height / 2;
            
            const relX = (clientX - centerX - offsetX) / scale + centerX;
            const relY = (clientY - centerY - offsetY) / scale + centerY;
            
            const x = Math.max(0, Math.min(rect.width, relX - rect.left));
            const y = Math.max(0, Math.min(rect.height, relY - rect.top));
            const desktopX = (x / rect.width) * this.desktopWidth;
            const desktopY = (y / rect.height) * this.desktopHeight;
            return { x: Math.round(desktopX), y: Math.round(desktopY) };
        } catch (e) {
            return { x: 0, y: 0 };
        }
    }
    
    setupTouchHandlers() {
        const layer = this.touchLayer;
        if (!layer) return;
        
        layer.addEventListener('touchstart', (e) => {
            try {
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
                    this.touchState.isPinching = false;
                    
                    this.touchState.longPressTimer = setTimeout(() => {
                        try {
                            this.touchState.isLongPress = true;
                            this.touchState.isDragging = true;
                            this._safeEmit('mouse:right:down');
                        } catch (e) {}
                    }, this.touchState.longPressDelay);
                    
                } else if (e.touches.length === 2) {
                    const center = this._getTouchCenter(e.touches);
                    this.touchState.lastCenterX = center.x;
                    this.touchState.lastCenterY = center.y;
                    this.touchState.lastPinchDist = this._getDistance(e.touches);
                    this.touchState.isPinching = true;
                    
                    if (this.touchState.longPressTimer) {
                        clearTimeout(this.touchState.longPressTimer);
                        this.touchState.longPressTimer = null;
                    }
                    if (this.touchState.isDragging && !this.touchState.isLongPress) {
                        this._safeEmit('mouse:left:up');
                        this.touchState.isDragging = false;
                    }
                }
            } catch (e) {
                console.error('Touchstart error:', e);
            }
        }, { passive: false });
        
        layer.addEventListener('touchmove', (e) => {
            try {
                e.preventDefault();
                e.stopPropagation();
                
                if (e.touches.length === 1 && this.touchState.active && !this.touchState.isPinching) {
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
                            if (this.viewState.scale > 1.0) {
                                this.viewState.offsetX += currentX - this.touchState.lastX;
                                this.viewState.offsetY += currentY - this.touchState.lastY;
                                this.applyViewTransform();
                            } else {
                                this.touchState.isDragging = true;
                                this._safeEmit('mouse:left:down');
                            }
                        }
                        
                        if (this.touchState.isDragging || this.viewState.scale <= 1.0) {
                            const moveDx = currentX - this.touchState.lastX;
                            const moveDy = currentY - this.touchState.lastY;
                            this._safeEmit('mouse:move:rel', {
                                dx: moveDx,
                                dy: moveDy
                            });
                        }
                    }
                    
                    this.touchState.lastX = currentX;
                    this.touchState.lastY = currentY;
                    
                } else if (e.touches.length === 2) {
                    const newDist = this._getDistance(e.touches);
                    const newCenter = this._getTouchCenter(e.touches);
                    
                    const scaleDelta = newDist / this.touchState.lastPinchDist;
                    const newScale = Math.max(
                        this.viewState.minScale,
                        Math.min(this.viewState.maxScale, this.viewState.scale * scaleDelta)
                    );
                    
                    this.viewState.scale = newScale;
                    
                    if (newScale <= 1.0) {
                        this.viewState.offsetX = 0;
                        this.viewState.offsetY = 0;
                    } else {
                        this.viewState.offsetX += newCenter.x - this.touchState.lastCenterX;
                        this.viewState.offsetY += newCenter.y - this.touchState.lastCenterY;
                    }
                    
                    this.applyViewTransform();
                    
                    this.touchState.lastPinchDist = newDist;
                    this.touchState.lastCenterX = newCenter.x;
                    this.touchState.lastCenterY = newCenter.y;
                }
            } catch (e) {
                console.error('Touchmove error:', e);
            }
        }, { passive: false });
        
        layer.addEventListener('touchend', (e) => {
            try {
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
                    } else if (this.touchState.active && !this.touchState.isPinching) {
                        const pos = this.screenToDesktop(this.touchState.startX, this.touchState.startY);
                        this._safeEmit('mouse:move:abs', pos);
                        this._safeEmit('mouse:left:click');
                    }
                    
                    this.touchState.active = false;
                    this.touchState.isLongPress = false;
                    this.touchState.isDragging = false;
                    this.touchState.isPinching = false;
                    this.touchState.fingers = 0;
                } else if (e.touches.length === 1) {
                    this.touchState.fingers = 1;
                    this.touchState.isPinching = false;
                    const touch = e.touches[0];
                    this.touchState.lastX = touch.clientX;
                    this.touchState.lastY = touch.clientY;
                }
            } catch (e) {
                console.error('Touchend error:', e);
            }
        }, { passive: false });
        
        layer.addEventListener('touchcancel', (e) => {
            try {
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
                this.touchState.isPinching = false;
                this.touchState.fingers = 0;
            } catch (e) {
                console.error('Touchcancel error:', e);
            }
        }, { passive: false });
        
        layer.addEventListener('contextmenu', (e) => e.preventDefault());
    }
    
    setupDraggableButton() {
        const btn = document.getElementById('keyboard-toggle');
        const keyboard = document.getElementById('virtual-keyboard');
        if (!btn || !keyboard) return;
        
        let isDragging = false;
        let startX, startY, startLeft, startTop;
        let hasMoved = false;
        
        const onTouchStart = (e) => {
            try {
                const touch = e.touches ? e.touches[0] : e;
                isDragging = true;
                hasMoved = false;
                startX = touch.clientX;
                startY = touch.clientY;
                
                const rect = btn.getBoundingClientRect();
                startLeft = rect.left;
                startTop = rect.top;
                
                btn.style.transition = 'none';
            } catch (e) {}
        };
        
        const onTouchMove = (e) => {
            if (!isDragging) return;
            try {
                e.preventDefault();
                const touch = e.touches ? e.touches[0] : e;
                const dx = touch.clientX - startX;
                const dy = touch.clientY - startY;
                
                if (Math.abs(dx) > 5 || Math.abs(dy) > 5) {
                    hasMoved = true;
                }
                
                let newLeft = startLeft + dx;
                let newTop = startTop + dy;
                
                const safeArea = 16;
                const maxLeft = window.innerWidth - btn.offsetWidth - safeArea;
                const maxTop = window.innerHeight - btn.offsetHeight - safeArea;
                
                newLeft = Math.max(safeArea, Math.min(maxLeft, newLeft));
                newTop = Math.max(safeArea, Math.min(maxTop, newTop));
                
                btn.style.left = newLeft + 'px';
                btn.style.top = newTop + 'px';
                btn.style.right = 'auto';
                btn.style.bottom = 'auto';
            } catch (e) {}
        };
        
        const onTouchEnd = (e) => {
            if (!isDragging) return;
            isDragging = false;
            btn.style.transition = '';
            
            if (!hasMoved) {
                keyboard.classList.toggle('collapsed');
            }
        };
        
        btn.addEventListener('touchstart', onTouchStart, { passive: true });
        btn.addEventListener('touchmove', onTouchMove, { passive: false });
        btn.addEventListener('touchend', onTouchEnd, { passive: true });
        btn.addEventListener('touchcancel', onTouchEnd, { passive: true });
        
        btn.addEventListener('mousedown', onTouchStart);
        document.addEventListener('mousemove', onTouchMove);
        document.addEventListener('mouseup', onTouchEnd);
        
        btn.addEventListener('dblclick', (e) => {
            e.preventDefault();
            this.resetView();
        });
    }
    
    setupKeyboard() {
        const keyboard = document.getElementById('virtual-keyboard');
        const closeBtn = document.getElementById('keyboard-close');
        
        if (closeBtn && keyboard) {
            closeBtn.addEventListener('click', () => {
                keyboard.classList.add('collapsed');
            });
        }
        
        try {
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
        } catch (e) {
            console.error('Keyboard setup error:', e);
        }
    }
    
    sendKeyWithModifiers(key) {
        try {
            if (this.activeModifiers.size > 0) {
                const keys = [...this.activeModifiers, key];
                this._safeEmit('key:combination', { keys });
                this.clearModifiers();
            } else {
                this._safeEmit('key:press', { key });
            }
        } catch (e) {}
    }
    
    clearModifiers() {
        try {
            document.querySelectorAll('.modifier-key').forEach(btn => {
                btn.classList.remove('active');
            });
            this.activeModifiers.clear();
        } catch (e) {}
    }
    
    setupTextInput() {
        try {
            const textInput = document.getElementById('text-input');
            const sendBtn = document.getElementById('send-text');
            
            if (!textInput || !sendBtn) return;
            
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
        } catch (e) {
            console.error('Text input setup error:', e);
        }
    }
}

document.addEventListener('DOMContentLoaded', () => {
    try {
        window.remoteDesktop = new RemoteDesktop();
    } catch (e) {
        console.error('Fatal init error:', e);
    }
});

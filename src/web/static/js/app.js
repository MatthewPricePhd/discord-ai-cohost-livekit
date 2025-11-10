/**
 * Main application JavaScript for Discord AI Co-Host Bot
 */

class AICoHostApp {
    constructor() {
        this.status = {
            running: false,
            mode: 'passive',
            discord_status: null,
            openai_status: null,
            web_server_running: false
        };
        
        this.updateInterval = null;
        this.init();
    }
    
    init() {
        this.setupEventListeners();
        this.startStatusUpdates();
        console.log('AI Co-Host Dashboard initialized');
    }
    
    setupEventListeners() {
        // Status refresh
        document.addEventListener('DOMContentLoaded', () => {
            this.updateStatus();
        });
        
        
        // Error handling
        window.addEventListener('error', (event) => {
            console.error('Application error:', event.error);
            this.showToast('An error occurred. Check the console for details.', 'error');
        });
    }
    
    async updateStatus() {
        try {
            const response = await fetch('/api/status');
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            
            const status = await response.json();
            this.status = status;
            
            this.updateStatusUI(status);
            
        } catch (error) {
            console.error('Failed to fetch status:', error);
            this.updateStatusUI({
                running: false,
                mode: 'unknown',
                discord_status: null,
                openai_status: null,
                web_server_running: false
            });
        }
    }
    
    updateStatusUI(status) {
        // Update connection indicator
        const connectionIndicator = document.getElementById('connection-indicator');
        const connectionText = document.getElementById('connection-text');
        
        if (connectionIndicator && connectionText) {
            if (status.running) {
                connectionIndicator.className = 'w-3 h-3 rounded-full bg-green-500 status-online';
                connectionText.textContent = 'Online';
            } else {
                connectionIndicator.className = 'w-3 h-3 rounded-full bg-red-500 status-offline';
                connectionText.textContent = 'Offline';
            }
        }
        
        // Update health indicator
        const healthIndicator = document.getElementById('health-indicator');
        const healthText = document.getElementById('health-text');
        
        if (healthIndicator && healthText) {
            const isHealthy = status.running && status.discord_status && status.discord_status.bot_ready;
            if (isHealthy) {
                healthIndicator.className = 'w-3 h-3 rounded-full bg-green-500';
                healthText.textContent = 'Healthy';
            } else if (status.running) {
                healthIndicator.className = 'w-3 h-3 rounded-full bg-yellow-500';
                healthText.textContent = 'Issues';
            } else {
                healthIndicator.className = 'w-3 h-3 rounded-full bg-red-500';
                healthText.textContent = 'Unhealthy';
            }
        }
        
        // Update mode indicator
        const modeIndicator = document.getElementById('mode-indicator');
        if (modeIndicator) {
            const isConnected = status.running && status.discord_status && status.discord_status.bot_ready;
            
            if (!isConnected) {
                modeIndicator.textContent = 'Inactive';
                modeIndicator.className = 'px-2 py-1 text-xs font-semibold rounded-full bg-red-600 text-white';
            } else if (status.mode === 'active') {
                modeIndicator.textContent = 'Active';
                modeIndicator.className = 'px-2 py-1 text-xs font-semibold rounded-full bg-green-600 text-white';
            } else {
                modeIndicator.textContent = 'Passive';
                modeIndicator.className = 'px-2 py-1 text-xs font-semibold rounded-full bg-gray-600 text-gray-200';
            }
        }
        
        // Update connection status details
        this.updateConnectionStatus(status);
    }
    
    updateConnectionStatus(status) {
        const discordStatus = document.getElementById('discord-status');
        const openaiStatus = document.getElementById('openai-status');
        const voiceStatus = document.getElementById('voice-status');
        const latency = document.getElementById('latency');
        
        if (discordStatus) {
            const discord = status.discord_status;
            if (discord && discord.bot_ready) {
                discordStatus.textContent = 'Connected';
                discordStatus.className = 'font-medium text-green-400';
            } else {
                discordStatus.textContent = 'Disconnected';
                discordStatus.className = 'font-medium text-red-400';
            }
        }
        
        if (openaiStatus) {
            const openai = status.openai_status;
            if (openai && openai.realtime_status && openai.realtime_status.connected) {
                openaiStatus.textContent = 'Connected';
                openaiStatus.className = 'font-medium text-green-400';
            } else {
                openaiStatus.textContent = 'Disconnected';
                openaiStatus.className = 'font-medium text-red-400';
            }
        }
        
        if (voiceStatus) {
            const discord = status.discord_status;
            if (discord && discord.voice_connection && discord.voice_connection.connected) {
                const channel = discord.voice_connection.channel_name;
                voiceStatus.textContent = `Connected to ${channel}`;
                voiceStatus.className = 'font-medium text-green-400';
            } else {
                voiceStatus.textContent = 'Not connected';
                voiceStatus.className = 'font-medium text-gray-400';
            }
        }
        
        if (latency) {
            const discord = status.discord_status;
            if (discord && discord.latency !== null) {
                latency.textContent = `${discord.latency}ms`;
                latency.className = discord.latency < 100 ? 'font-medium text-green-400' : 
                                  discord.latency < 200 ? 'font-medium text-yellow-400' : 
                                  'font-medium text-red-400';
            } else {
                latency.textContent = '--ms';
                latency.className = 'font-medium text-gray-400';
            }
        }
    }
    
    startStatusUpdates() {
        // Update immediately
        this.updateStatus();
        
        // Then update every 5 seconds
        this.updateInterval = setInterval(() => {
            this.updateStatus();
        }, 5000);
    }
    
    stopStatusUpdates() {
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
            this.updateInterval = null;
        }
    }
    
    showToast(message, type = 'info', duration = 5000) {
        const container = document.getElementById('toast-container');
        if (!container) return;
        
        const toast = document.createElement('div');
        toast.className = `toast ${type} hide`;
        
        const icon = {
            success: 'fa-check-circle',
            error: 'fa-exclamation-circle',
            warning: 'fa-exclamation-triangle',
            info: 'fa-info-circle'
        }[type] || 'fa-info-circle';
        
        toast.innerHTML = `
            <div class="flex items-center">
                <i class="fas ${icon} mr-2"></i>
                <span class="flex-1">${message}</span>
                <button class="ml-2 text-white hover:text-gray-200" onclick="this.parentElement.parentElement.remove()">
                    <i class="fas fa-times"></i>
                </button>
            </div>
        `;
        
        container.appendChild(toast);
        
        // Trigger show animation
        setTimeout(() => {
            toast.classList.remove('hide');
            toast.classList.add('show');
        }, 100);
        
        // Auto-remove after duration
        setTimeout(() => {
            toast.classList.remove('show');
            toast.classList.add('hide');
            setTimeout(() => {
                if (toast.parentElement) {
                    toast.remove();
                }
            }, 300);
        }, duration);
    }
    
    showLoading(show = true) {
        const overlay = document.getElementById('loading-overlay');
        if (overlay) {
            overlay.classList.toggle('hidden', !show);
        }
    }
    
    formatTimestamp(timestamp) {
        return new Date(timestamp * 1000).toLocaleTimeString();
    }
    
    formatFileSize(bytes) {
        const sizes = ['B', 'KB', 'MB', 'GB'];
        if (bytes === 0) return '0 B';
        const i = Math.floor(Math.log(bytes) / Math.log(1024));
        return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${sizes[i]}`;
    }
    
    
    // Cleanup on page unload
    cleanup() {
        this.stopStatusUpdates();
    }
}

// Global app instance
let app;

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    app = new AICoHostApp();
    // Make app globally available for other scripts
    window.app = app;
});

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (app) {
        app.cleanup();
    }
});

// Export for other scripts
window.AICoHostApp = AICoHostApp;
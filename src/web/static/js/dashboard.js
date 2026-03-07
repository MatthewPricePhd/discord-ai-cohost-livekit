/**
 * Dashboard-specific JavaScript for Discord AI Co-Host Bot
 */

class Dashboard {
    constructor() {
        this.guilds = [];
        this.documents = [];
        this.transcript = [];
        this.isPassiveMode = true;
        this.startTime = Date.now();
        
        this.init();
    }
    
    init() {
        this.setupEventListeners();
        this.loadGuilds();
        this.loadDocuments();
        this.loadTranscript();
        this.loadStatus();
        this.startStatusPolling();
        this.loadSessionStatus();
        this.loadProviders();

        // Initialize split-stack mode display
        this.updateModeDisplay('passive');
    }
    
    setupEventListeners() {
        // Voice channel controls
        const joinBtn = document.getElementById('join-btn');
        const leaveBtn = document.getElementById('leave-btn');
        const channelSelect = document.getElementById('channel-select');
        
        if (joinBtn) {
            joinBtn.addEventListener('click', () => this.joinVoiceChannel());
        }
        
        if (leaveBtn) {
            leaveBtn.addEventListener('click', () => this.leaveVoiceChannel());
        }
        
        // Split-stack mode controls
        const modeButtons = document.querySelectorAll('.mode-btn');
        modeButtons.forEach(btn => {
            btn.addEventListener('click', () => this.setMode(btn.dataset.mode));
        });
        
        // Provider and model selection dropdowns
        const reasoningModelSelect = document.getElementById('reasoning-model-select');
        const ttsProviderSelect = document.getElementById('tts-provider-select');
        const sttProviderSelect = document.getElementById('stt-provider-select');
        const ttsVoiceSelect = document.getElementById('tts-voice-select');

        if (reasoningModelSelect) {
            reasoningModelSelect.addEventListener('change', () => this.setReasoningModel(reasoningModelSelect.value));
        }
        if (ttsProviderSelect) {
            ttsProviderSelect.addEventListener('change', () => this.setTTSProvider(ttsProviderSelect.value));
        }
        if (sttProviderSelect) {
            sttProviderSelect.addEventListener('change', () => this.setSTTProvider(sttProviderSelect.value));
        }
        if (ttsVoiceSelect) {
            ttsVoiceSelect.addEventListener('change', () => this.selectVoice(ttsVoiceSelect.value));
        }
        
        // Force response
        const forceResponse = document.getElementById('force-response');
        if (forceResponse) {
            forceResponse.addEventListener('click', () => this.forceResponse());
        }
        
        // Document upload
        const uploadBtn = document.getElementById('upload-btn');
        const documentUpload = document.getElementById('document-upload');
        
        if (uploadBtn && documentUpload) {
            uploadBtn.addEventListener('click', () => documentUpload.click());
            documentUpload.addEventListener('change', (e) => this.handleFileUpload(e));
        }
        
        // Drag and drop for document upload
        const uploadArea = uploadBtn ? uploadBtn.parentElement : null;
        if (uploadArea) {
            uploadArea.addEventListener('dragover', (e) => {
                e.preventDefault();
                uploadArea.classList.add('drag-over');
            });
            
            uploadArea.addEventListener('dragleave', (e) => {
                e.preventDefault();
                uploadArea.classList.remove('drag-over');
            });
            
            uploadArea.addEventListener('drop', (e) => {
                e.preventDefault();
                uploadArea.classList.remove('drag-over');
                this.handleFileUpload(e);
            });
        }
        
        // Transcript refresh
        const refreshTranscript = document.getElementById('refresh-transcript');
        if (refreshTranscript) {
            refreshTranscript.addEventListener('click', () => {
                this.lastRefreshWasManual = true;
                this.loadTranscript();
            });
        }
        
        // Generate summary
        const generateSummary = document.getElementById('generate-summary');
        if (generateSummary) {
            generateSummary.addEventListener('click', () => this.generateSummary());
        }
        
        // ChatGPT functionality
        const chatgptSend = document.getElementById('chatgpt-send');
        const chatgptInput = document.getElementById('chatgpt-input');
        console.log('ChatGPT elements found:', { 
            sendBtn: !!chatgptSend, 
            inputField: !!chatgptInput 
        });
        
        if (chatgptSend) {
            chatgptSend.addEventListener('click', () => {
                console.log('ChatGPT button clicked!');
                this.askChatGPT();
            });
        }
        if (chatgptInput) {
            chatgptInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter' && e.ctrlKey) {
                    console.log('ChatGPT Ctrl+Enter pressed!');
                    this.askChatGPT();
                }
            });
        }
        
        // ChatGPT response controls
        const clearChatGPT = document.getElementById('clear-chatgpt');
        const chatgptToContext = document.getElementById('chatgpt-to-context');
        if (clearChatGPT) {
            clearChatGPT.addEventListener('click', () => this.clearChatGPTResponse());
        }
        if (chatgptToContext) {
            chatgptToContext.addEventListener('click', () => this.sendChatGPTToContext());
        }
        
        // Documents to context
        const docsToContext = document.getElementById('docs-to-context');
        if (docsToContext) {
            docsToContext.addEventListener('click', () => this.sendDocumentsToContext());
        }
        
        // Export buttons
        const exportTranscript = document.getElementById('export-transcript');
        const exportContext = document.getElementById('export-context');
        if (exportTranscript) {
            exportTranscript.addEventListener('click', () => this.exportTranscript());
        }
        if (exportContext) {
            exportContext.addEventListener('click', () => this.exportContext());
        }
        
        // Session spend widget
        const sessionStart = document.getElementById('session-start');
        const sessionStop = document.getElementById('session-stop');
        if (sessionStart) {
            sessionStart.addEventListener('click', () => this.startSession());
        }
        if (sessionStop) {
            sessionStop.addEventListener('click', () => this.stopSession());
        }
    }
    
    async loadGuilds() {
        try {
            const response = await fetch('/api/discord/guilds');
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            
            const data = await response.json();
            this.guilds = data.guilds || [];
            this.updateChannelSelect();
            
        } catch (error) {
            console.error('Failed to load guilds:', error);
            this.showToast('Failed to load Discord channels', 'error');
        }
    }
    
    updateChannelSelect() {
        const select = document.getElementById('channel-select');
        if (!select) return;
        
        // Clear existing options except the first
        while (select.children.length > 1) {
            select.removeChild(select.lastChild);
        }
        
        this.guilds.forEach(guild => {
            if (guild.voice_channels && guild.voice_channels.length > 0) {
                // Add guild header
                const guildGroup = document.createElement('optgroup');
                guildGroup.label = guild.name;
                
                guild.voice_channels.forEach(channel => {
                    const option = document.createElement('option');
                    option.value = channel.id;
                    option.textContent = `${channel.name} (${channel.members.length} members)`;
                    guildGroup.appendChild(option);
                });
                
                select.appendChild(guildGroup);
            }
        });
    }
    
    async joinVoiceChannel() {
        const select = document.getElementById('channel-select');
        const channelId = select?.value;
        
        if (!channelId) {
            this.showDiscordVoiceMessage('Please select a voice channel first', 'warning');
            return;
        }
        
        const joinBtn = document.getElementById('join-btn');
        const originalContent = joinBtn?.innerHTML;
        
        try {
            if (joinBtn) {
                joinBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
                joinBtn.disabled = true;
            }
            
            const response = await fetch('/api/voice/join', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ channel_id: parseInt(channelId) })
            });
            
            const result = await response.json();
            
            if (response.ok) {
                this.showDiscordVoiceMessage('Joined voice channel successfully', 'success');
                this.startTranscriptPolling();
            } else {
                this.showDiscordVoiceMessage(result.detail || 'Failed to join voice channel', 'error');
            }
            
        } catch (error) {
            console.error('Error joining voice channel:', error);
            this.showDiscordVoiceMessage('Failed to join voice channel', 'error');
        } finally {
            if (joinBtn) {
                joinBtn.innerHTML = originalContent;
                joinBtn.disabled = false;
            }
        }
    }
    
    async leaveVoiceChannel() {
        const leaveBtn = document.getElementById('leave-btn');
        const originalContent = leaveBtn?.innerHTML;
        
        try {
            if (leaveBtn) {
                leaveBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
                leaveBtn.disabled = true;
            }
            
            const response = await fetch('/api/voice/leave', {
                method: 'POST'
            });
            
            const result = await response.json();
            
            if (response.ok) {
                this.showDiscordVoiceMessage('Left voice channel successfully', 'success');
                this.stopTranscriptPolling();
            } else {
                this.showDiscordVoiceMessage(result.detail || 'Failed to leave voice channel', 'error');
            }
            
        } catch (error) {
            console.error('Error leaving voice channel:', error);
            this.showDiscordVoiceMessage('Failed to leave voice channel', 'error');
        } finally {
            if (leaveBtn) {
                leaveBtn.innerHTML = originalContent;
                leaveBtn.disabled = false;
            }
        }
    }
    
    async toggleMode() {
        const modeToggle = document.getElementById('mode-toggle');
        const currentMode = document.getElementById('current-mode');
        const modeDescription = document.getElementById('mode-description');
        
        const originalContent = modeToggle?.innerHTML;
        
        try {
            if (modeToggle) {
                modeToggle.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
                modeToggle.disabled = true;
            }
            
            const response = await fetch('/api/mode/toggle', {
                method: 'POST'
            });
            
            const result = await response.json();
            
            if (response.ok) {
                this.isPassiveMode = result.mode === 'passive';
                
                if (currentMode) {
                    currentMode.textContent = result.mode.charAt(0).toUpperCase() + result.mode.slice(1);
                }
                
                if (modeDescription) {
                    modeDescription.textContent = this.isPassiveMode 
                        ? 'Listening and building context'
                        : 'Active and ready to respond';
                }
                
                if (modeToggle) {
                    modeToggle.textContent = this.isPassiveMode ? 'Activate' : 'Deactivate';
                }
                
                this.showAIModeMessage(`Switched to ${result.mode} mode`, 'success');
                
            } else {
                this.showAIModeMessage(result.detail || 'Failed to toggle mode', 'error');
            }
            
        } catch (error) {
            console.error('Error toggling mode:', error);
            this.showAIModeMessage('Failed to toggle mode', 'error');
        } finally {
            if (modeToggle) {
                modeToggle.innerHTML = originalContent;
                modeToggle.disabled = false;
            }
        }
    }
    
    // Split-stack architecture methods
    async setMode(mode) {
        const modeButtons = document.querySelectorAll('.mode-btn');
        const currentModeDisplay = document.getElementById('current-mode');
        const modeDescription = document.getElementById('mode-description');
        const modeStatusIndicator = document.getElementById('mode-status-indicator');
        
        // Disable all mode buttons during transition
        modeButtons.forEach(btn => btn.disabled = true);
        
        try {
            let endpoint;
            switch (mode) {
                case 'passive':
                    endpoint = '/api/mode/passive';
                    break;
                case 'speech-to-speech':
                    endpoint = '/api/mode/speech-to-speech';
                    break;
                case 'ask-chatgpt':
                    // This mode is handled differently - it's temporary
                    this.showAIModeMessage('Ask ChatGPT mode activated - use the query box below', 'info');
                    return;
                default:
                    throw new Error('Invalid mode');
            }
            
            const response = await fetch(endpoint, {
                method: 'POST'
            });
            
            const result = await response.json();
            
            if (response.ok) {
                // Update UI to reflect new mode
                this.updateModeDisplay(mode);
                this.showAIModeMessage(`Switched to ${this.getModeDisplayName(mode)} mode`, 'success');
                
            } else {
                this.showAIModeMessage(result.detail || 'Failed to switch mode', 'error');
            }
            
        } catch (error) {
            console.error('Error setting mode:', error);
            this.showAIModeMessage('Failed to switch mode', 'error');
        } finally {
            // Re-enable mode buttons
            modeButtons.forEach(btn => btn.disabled = false);
        }
    }
    
    updateModeDisplay(mode) {
        const currentModeDisplay = document.getElementById('current-mode');
        const modeDescription = document.getElementById('mode-description');
        const modeStatusIndicator = document.getElementById('mode-status-indicator');
        const modeButtons = document.querySelectorAll('.mode-btn');
        
        // Update mode buttons styling
        modeButtons.forEach(btn => {
            if (btn.dataset.mode === mode) {
                btn.classList.remove('bg-gray-600', 'hover:bg-gray-500');
                btn.classList.add('bg-blue-600', 'hover:bg-blue-500', 'ring-2', 'ring-blue-400');
            } else {
                btn.classList.remove('bg-blue-600', 'hover:bg-blue-500', 'ring-2', 'ring-blue-400');
                btn.classList.add('bg-gray-600', 'hover:bg-gray-500');
            }
        });
        
        // Update mode display
        if (currentModeDisplay) {
            currentModeDisplay.textContent = this.getModeDisplayName(mode);
        }
        
        // Update description
        if (modeDescription) {
            const descriptions = {
                'passive': 'Transcription-only mode active',
                'speech-to-speech': 'Full voice interaction enabled',
                'ask-chatgpt': 'Text-only query mode'
            };
            modeDescription.textContent = descriptions[mode] || 'Unknown mode';
        }
        
        // Update status indicator color
        if (modeStatusIndicator) {
            modeStatusIndicator.className = 'w-3 h-3 rounded-full animate-pulse';
            const colors = {
                'passive': 'bg-blue-400',
                'speech-to-speech': 'bg-green-400',
                'ask-chatgpt': 'bg-purple-400'
            };
            modeStatusIndicator.classList.add(colors[mode] || 'bg-gray-400');
        }
        
        // Store current mode
        this.currentMode = mode;
    }
    
    getModeDisplayName(mode) {
        const names = {
            'passive': 'Passive Listening',
            'speech-to-speech': 'Speech-to-Speech',
            'ask-chatgpt': 'Ask ChatGPT'
        };
        return names[mode] || mode;
    }
    
    async loadProviders() {
        try {
            const response = await fetch('/api/providers');
            if (!response.ok) return;
            const data = await response.json();

            // Set current values in dropdowns
            const reasoningSelect = document.getElementById('reasoning-model-select');
            const ttsProviderSelect = document.getElementById('tts-provider-select');
            const sttProviderSelect = document.getElementById('stt-provider-select');

            if (reasoningSelect) reasoningSelect.value = data.reasoning_model || 'gpt-5.4';
            if (ttsProviderSelect) {
                // Disable elevenlabs option if not available
                const elOption = ttsProviderSelect.querySelector('option[value="elevenlabs"]');
                if (elOption && !data.elevenlabs_available) elOption.disabled = true;
                ttsProviderSelect.value = data.tts_provider || 'openai';
            }
            if (sttProviderSelect) {
                const elOption = sttProviderSelect.querySelector('option[value="elevenlabs"]');
                if (elOption && !data.elevenlabs_available) elOption.disabled = true;
                sttProviderSelect.value = data.stt_provider || 'openai';
            }

            // Load voices for current provider
            await this.loadVoices();
        } catch (error) {
            // Silently fail on initial load
        }
    }

    async loadVoices() {
        try {
            const response = await fetch('/api/voices');
            if (!response.ok) return;
            const data = await response.json();
            const voiceSelect = document.getElementById('tts-voice-select');
            if (!voiceSelect) return;

            voiceSelect.innerHTML = '';
            (data.voices || []).forEach(v => {
                const opt = document.createElement('option');
                opt.value = v.id;
                opt.textContent = v.name;
                voiceSelect.appendChild(opt);
            });
        } catch (error) {
            // Silently fail
        }
    }

    async setReasoningModel(model) {
        try {
            const response = await fetch('/api/providers/reasoning-model', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ model })
            });
            const result = await response.json();
            if (response.ok) {
                this.showModelSelectionMessage(`Reasoning model: ${model}`, 'success');
            } else {
                this.showModelSelectionMessage(result.detail || 'Failed to update', 'error');
            }
        } catch (error) {
            this.showModelSelectionMessage('Failed to update reasoning model', 'error');
        }
    }

    async setTTSProvider(provider) {
        try {
            const response = await fetch('/api/providers/tts', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ provider })
            });
            const result = await response.json();
            if (response.ok) {
                this.showModelSelectionMessage(`TTS: ${provider}`, 'success');
                await this.loadVoices();
            } else {
                this.showModelSelectionMessage(result.detail || 'Failed to update', 'error');
                // Revert dropdown
                await this.loadProviders();
            }
        } catch (error) {
            this.showModelSelectionMessage('Failed to update TTS provider', 'error');
        }
    }

    async setSTTProvider(provider) {
        try {
            const response = await fetch('/api/providers/stt', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ provider })
            });
            const result = await response.json();
            if (response.ok) {
                this.showModelSelectionMessage(`STT: ${provider}`, 'success');
            } else {
                this.showModelSelectionMessage(result.detail || 'Failed to update', 'error');
                await this.loadProviders();
            }
        } catch (error) {
            this.showModelSelectionMessage('Failed to update STT provider', 'error');
        }
    }

    async selectVoice(voiceId) {
        try {
            const response = await fetch('/api/voices/select', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ voice_id: voiceId })
            });
            const result = await response.json();
            if (response.ok) {
                this.showModelSelectionMessage('Voice updated', 'success');
            } else {
                this.showModelSelectionMessage(result.detail || 'Failed to update voice', 'error');
            }
        } catch (error) {
            this.showModelSelectionMessage('Failed to update voice', 'error');
        }
    }
    
    async forceResponse() {
        const forceBtn = document.getElementById('force-response');
        const originalContent = forceBtn?.innerHTML;
        
        try {
            if (forceBtn) {
                forceBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Generating...';
                forceBtn.disabled = true;
            }
            
            const response = await fetch('/api/ai/respond', {
                method: 'POST'
            });
            
            const result = await response.json();
            
            if (response.ok) {
                this.showAIModeMessage('AI response triggered', 'success');
            } else {
                this.showAIModeMessage(result.detail || 'Failed to trigger AI response', 'error');
            }
            
        } catch (error) {
            console.error('Error forcing AI response:', error);
            this.showAIModeMessage('Failed to trigger AI response', 'error');
        } finally {
            if (forceBtn) {
                forceBtn.innerHTML = originalContent;
                forceBtn.disabled = false;
            }
        }
    }
    
    async handleFileUpload(event) {
        let files;
        
        if (event.dataTransfer) {
            files = Array.from(event.dataTransfer.files);
        } else {
            files = Array.from(event.target.files);
        }
        
        if (files.length === 0) return;
        
        app.showLoading(true);
        
        try {
            for (const file of files) {
                await this.uploadFile(file);
            }
            
            await this.loadDocuments();
            this.showDocumentsMessage(`Successfully uploaded ${files.length} file(s)`, 'success');
            
        } catch (error) {
            console.error('Error uploading files:', error);
            this.showDocumentsMessage('Failed to upload files', 'error');
        } finally {
            app.showLoading(false);
            
            // Clear file input
            const fileInput = document.getElementById('document-upload');
            if (fileInput) {
                fileInput.value = '';
            }
        }
    }
    
    async uploadFile(file) {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('title', file.name);
        
        const response = await fetch('/api/documents/upload', {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Upload failed');
        }
        
        return await response.json();
    }
    
    async loadDocuments() {
        try {
            const response = await fetch('/api/documents');
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            
            const data = await response.json();
            this.documents = data.documents || [];
            this.updateDocumentsList();
            
        } catch (error) {
            console.error('Failed to load documents:', error);
        }
    }
    
    updateDocumentsList() {
        const container = document.getElementById('documents-list');
        if (!container) return;
        
        if (this.documents.length === 0) {
            container.innerHTML = `
                <div class="text-gray-500 text-center py-4">
                    <i class="fas fa-folder-open text-xl mb-2"></i>
                    <p>No documents uploaded yet.</p>
                </div>
            `;
            return;
        }
        
        container.innerHTML = this.documents.map(doc => `
            <div class="document-item">
                <div class="info">
                    <div class="icon">
                        <i class="fas fa-file-alt"></i>
                    </div>
                    <div class="details">
                        <div class="name">${doc.name}</div>
                        <div class="meta">${this.formatFileSize(doc.size)} • ${doc.type}</div>
                    </div>
                </div>
                <div class="actions">
                    <button class="text-red-400 hover:text-red-300" onclick="dashboard.deleteDocument('${doc.id}')">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            </div>
        `).join('');
    }
    
    async deleteDocument(documentId) {
        if (!confirm('Are you sure you want to delete this document?')) {
            return;
        }
        
        try {
            const response = await fetch(`/api/documents/${documentId}`, {
                method: 'DELETE'
            });
            
            const result = await response.json();
            
            if (response.ok) {
                this.showDocumentsMessage('Document deleted successfully', 'success');
                await this.loadDocuments();
            } else {
                this.showDocumentsMessage(result.detail || 'Failed to delete document', 'error');
            }
            
        } catch (error) {
            console.error('Error deleting document:', error);
            this.showDocumentsMessage('Failed to delete document', 'error');
        }
    }
    
    async loadTranscript() {
        try {
            const response = await fetch('/api/conversation/transcript');
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            
            const data = await response.json();
            this.transcript = data.turns || [];
            this.updateTranscript();
            
            // Show refresh message when manually triggered
            if (this.lastRefreshWasManual) {
                this.showLiveConversationMessage(`Refreshed conversation (${data.turns?.length || 0} turns)`, 'info');
                this.lastRefreshWasManual = false;
            }
            
        } catch (error) {
            console.error('Failed to load transcript:', error);
            this.showLiveConversationMessage('Failed to refresh conversation', 'error');
        }
    }
    
    updateTranscript() {
        const container = document.getElementById('transcript-container');
        if (!container) return;
        
        if (this.transcript.length === 0) {
            container.innerHTML = `
                <div class="text-gray-500 text-center py-8">
                    <i class="fas fa-microphone-slash text-2xl mb-2"></i>
                    <p>No conversation yet. Join a voice channel to start listening.</p>
                </div>
            `;
            return;
        }
        
        const transcriptHTML = this.transcript.map(turn => `
            <div class="transcript-entry ${turn.speaker.toLowerCase() === 'user' ? 'user' : 'ai'}">
                <div class="speaker">${turn.speaker}</div>
                <div class="content">${turn.text}</div>
                <div class="timestamp">${app.formatTimestamp(turn.timestamp)}</div>
            </div>
        `).join('');
        
        container.innerHTML = transcriptHTML;
        
        // Auto-scroll to bottom
        container.scrollTop = container.scrollHeight;
    }
    
    async generateSummary() {
        // The GENERATE button should create a new AI summary from conversation history
        const generateBtn = document.getElementById('generate-summary');
        const originalContent = generateBtn?.innerHTML;
        
        try {
            if (generateBtn) {
                generateBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-1"></i>Generating...';
                generateBtn.disabled = true;
            }
            
            // Call the conversation summarize endpoint to generate new summary
            const response = await fetch('/api/conversation/summarize', {
                method: 'POST'
            });
            
            const result = await response.json();
            
            if (response.ok) {
                // Update the context summary display with the new generated summary
                this.updateContextSummary(result.summary);
                this.showContextMessage('New context summary generated from conversation', 'success');
            } else {
                this.showContextMessage(result.detail || 'Failed to generate summary', 'error');
            }
            
        } catch (error) {
            console.error('Error generating summary:', error);
            this.showContextMessage('Failed to generate summary', 'error');
        } finally {
            if (generateBtn) {
                generateBtn.innerHTML = originalContent;
                generateBtn.disabled = false;
            }
        }
    }
    
    updateContextSummary(summary) {
        const container = document.getElementById('context-summary');
        if (!container) return;
        
        if (!summary || summary.trim() === '') {
            container.innerHTML = `
                <div class="text-gray-500 text-center py-4">
                    <i class="fas fa-lightbulb text-xl mb-2"></i>
                    <p>Context summary will appear here after conversation analysis.</p>
                </div>
            `;
            return;
        }
        
        // Simple formatting for summary text
        const formattedSummary = summary
            .replace(/\n\n/g, '</p><p>')
            .replace(/\n/g, '<br>')
            .replace(/^/, '<p>')
            .replace(/$/, '</p>');
        
        container.innerHTML = `
            <div class="context-summary">
                ${formattedSummary}
            </div>
        `;
    }
    
    startTranscriptPolling() {
        // Start polling for transcript updates every 5 seconds
        this.transcriptInterval = setInterval(() => {
            this.loadTranscript();
        }, 5000);
    }
    
    stopTranscriptPolling() {
        if (this.transcriptInterval) {
            clearInterval(this.transcriptInterval);
            this.transcriptInterval = null;
        }
    }
    
    async loadStatus() {
        try {
            const response = await fetch('/api/status');
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            
            const data = await response.json();
            this.updateStatus(data);
            
        } catch (error) {
            console.error('Failed to load status:', error);
            this.updateStatus({
                running: false,
                mode: 'unknown',
                discord_status: null,
                openai_status: null
            });
        }
    }
    
    updateStatus(status) {
        // Update header status bar elements
        this.updateHeaderStatus(status);
        
        // Update separate status indicators
        this.updateConnectionStatus(status);
        this.updateHealthStatus(status);
        this.updateModeStatus(status);
        
        // Update export button states
        this.updateExportButtonStates(status);
        
        // Update control panel mode display
        this.isPassiveMode = status.mode === 'passive';
        const currentMode = document.getElementById('current-mode');
        const modeDescription = document.getElementById('mode-description');
        const modeToggle = document.getElementById('mode-toggle');
        
        if (currentMode) {
            currentMode.textContent = status.mode.charAt(0).toUpperCase() + status.mode.slice(1);
        }
        
        if (modeDescription) {
            modeDescription.textContent = this.isPassiveMode 
                ? 'Listening and building context'
                : 'Active and ready to respond';
        }
        
        if (modeToggle) {
            modeToggle.textContent = this.isPassiveMode ? 'Activate' : 'Deactivate';
        }
    }
    
    updateExportButtonStates(status) {
        const exportTranscriptBtn = document.getElementById('export-transcript');
        const exportContextBtn = document.getElementById('export-context');
        
        // Determine if exports should be enabled
        const isConnected = status.discord_status && status.discord_status.voice_connection && 
                           status.discord_status.voice_connection.connected;
        const isPassive = status.mode === 'passive';
        const canExport = !isConnected || isPassive;
        
        if (exportTranscriptBtn) {
            exportTranscriptBtn.disabled = !canExport || this.transcript.length === 0;
            exportTranscriptBtn.title = canExport ? 
                (this.transcript.length === 0 ? 'No conversation to export' : 'Export conversation transcript') :
                'Export disabled during active transcription';
        }
        
        if (exportContextBtn) {
            const hasContext = document.getElementById('context-summary').textContent.trim() !== '';
            exportContextBtn.disabled = !canExport || !hasContext;
            exportContextBtn.title = canExport ? 
                (!hasContext ? 'No context to export' : 'Export context summary') :
                'Export disabled during active mode';
        }
    }
    
    startStatusPolling() {
        // Poll status every 10 seconds
        this.statusInterval = setInterval(() => {
            this.loadStatus();
        }, 10000);
    }
    
    stopStatusPolling() {
        if (this.statusInterval) {
            clearInterval(this.statusInterval);
            this.statusInterval = null;
        }
    }
    
    updateHeaderStatus(status) {
        // Update Discord status in header
        const headerDiscordStatus = document.getElementById('header-discord-status');
        if (headerDiscordStatus) {
            if (status.discord_status && status.discord_status.bot_user) {
                headerDiscordStatus.textContent = 'Connected';
                headerDiscordStatus.className = 'font-medium text-green-400';
            } else {
                headerDiscordStatus.textContent = 'Offline';
                headerDiscordStatus.className = 'font-medium text-red-400';
            }
        }
        
        // Update OpenAI status in header
        const headerOpenaiStatus = document.getElementById('header-openai-status');
        if (headerOpenaiStatus) {
            if (status.openai_status && status.openai_status.realtime_status && status.openai_status.realtime_status.connected) {
                headerOpenaiStatus.textContent = 'Connected';
                headerOpenaiStatus.className = 'font-medium text-green-400';
            } else {
                headerOpenaiStatus.textContent = 'Offline';
                headerOpenaiStatus.className = 'font-medium text-red-400';
            }
        }
        
        // Update Voice status in header
        const headerVoiceStatus = document.getElementById('header-voice-status');
        if (headerVoiceStatus) {
            if (status.discord_status && status.discord_status.voice_connection && status.discord_status.voice_connection.connected) {
                const channelName = status.discord_status.voice_connection.channel_name;
                headerVoiceStatus.textContent = channelName || 'Connected';
                headerVoiceStatus.className = 'font-medium text-green-400';
            } else {
                headerVoiceStatus.textContent = 'Not connected';
                headerVoiceStatus.className = 'font-medium text-gray-400';
            }
        }
        
        // Update Latency in header
        const headerLatency = document.getElementById('header-latency');
        if (headerLatency) {
            if (status.discord_status && status.discord_status.latency !== null) {
                headerLatency.textContent = `${Math.round(status.discord_status.latency)}ms`;
                headerLatency.className = 'font-medium text-green-400';
            } else {
                headerLatency.textContent = '--ms';
                headerLatency.className = 'font-medium text-gray-400';
            }
        }
        
        // Update mode indicator
        const modeIndicator = document.getElementById('mode-indicator');
        if (modeIndicator) {
            const mode = status.mode || 'unknown';
            modeIndicator.textContent = mode.charAt(0).toUpperCase() + mode.slice(1);
            
            if (mode === 'active') {
                modeIndicator.className = 'px-2 py-1 text-xs font-semibold rounded-full bg-green-600 text-white';
            } else if (mode === 'passive') {
                modeIndicator.className = 'px-2 py-1 text-xs font-semibold rounded-full bg-blue-600 text-white';
            } else {
                modeIndicator.className = 'px-2 py-1 text-xs font-semibold rounded-full bg-gray-600 text-gray-200';
            }
        }
    }
    
    
    updateConnectionStatus(status) {
        const connectionIndicator = document.getElementById('connection-indicator');
        const connectionText = document.getElementById('connection-text');
        
        const isConnected = status.running && status.discord_status && status.discord_status.bot_user;
        
        if (connectionIndicator) {
            if (isConnected) {
                connectionIndicator.className = 'w-3 h-3 rounded-full bg-green-500';
            } else {
                connectionIndicator.className = 'w-3 h-3 rounded-full bg-red-500';
            }
        }
        
        if (connectionText) {
            connectionText.textContent = isConnected ? 'Online' : 'Offline';
        }
    }
    
    updateHealthStatus(status) {
        const healthIndicator = document.getElementById('health-indicator');
        const healthText = document.getElementById('health-text');
        
        // Health considers multiple factors
        const discordHealthy = status.discord_status && status.discord_status.bot_user;
        const openaiHealthy = status.openai_status && status.openai_status.realtime_status;
        const isHealthy = status.running && discordHealthy && openaiHealthy;
        
        if (healthIndicator) {
            if (isHealthy) {
                healthIndicator.className = 'w-3 h-3 rounded-full bg-green-500';
            } else if (status.running) {
                healthIndicator.className = 'w-3 h-3 rounded-full bg-yellow-500';
            } else {
                healthIndicator.className = 'w-3 h-3 rounded-full bg-red-500';
            }
        }
        
        if (healthText) {
            if (isHealthy) {
                healthText.textContent = 'Healthy';
            } else if (status.running) {
                healthText.textContent = 'Issues';
            } else {
                healthText.textContent = 'Unhealthy';
            }
        }
    }
    
    updateModeStatus(status) {
        const modeIndicator = document.getElementById('mode-indicator');
        
        if (!modeIndicator) return;
        
        // Determine mode based on connectivity and settings
        const isConnected = status.running && status.discord_status && status.discord_status.bot_user;
        const canReceiveAudio = status.discord_status && status.discord_status.voice_connection && 
                               status.discord_status.voice_connection.connected;
        
        if (!isConnected) {
            // Bot not connected - Inactive (red)
            modeIndicator.textContent = 'Inactive';
            modeIndicator.className = 'px-2 py-1 text-xs font-semibold rounded-full bg-red-600 text-white';
        } else if (status.mode === 'active' && canReceiveAudio) {
            // Active mode and can receive audio - Active (green)
            modeIndicator.textContent = 'Active';
            modeIndicator.className = 'px-2 py-1 text-xs font-semibold rounded-full bg-green-600 text-white';
        } else {
            // Passive mode or connected but no audio - Passive (gray)
            modeIndicator.textContent = 'Passive';
            modeIndicator.className = 'px-2 py-1 text-xs font-semibold rounded-full bg-gray-600 text-gray-200';
        }
    }
    
    
    formatUptime(ms) {
        const seconds = Math.floor(ms / 1000);
        const minutes = Math.floor(seconds / 60);
        const hours = Math.floor(minutes / 60);
        const days = Math.floor(hours / 24);
        
        if (days > 0) {
            return `${days}d ${hours % 24}h`;
        } else if (hours > 0) {
            return `${hours}h ${minutes % 60}m`;
        } else if (minutes > 0) {
            return `${minutes}m ${seconds % 60}s`;
        } else {
            return `${seconds}s`;
        }
    }
    
    async askChatGPT() {
        console.log('askChatGPT method called!');
        const input = document.getElementById('chatgpt-input');
        const sendBtn = document.getElementById('chatgpt-send');
        const responseContainer = document.getElementById('chatgpt-response');
        
        console.log('Elements in askChatGPT:', {
            input: !!input,
            sendBtn: !!sendBtn,
            responseContainer: !!responseContainer,
            inputValue: input?.value
        });
        
        if (!input || !input.value.trim()) {
            console.log('Empty input detected, showing warning');
            this.showChatGPTMessage('Please enter a question for ChatGPT', 'warning');
            return;
        }
        
        const prompt = input.value.trim();
        const originalBtnContent = sendBtn?.innerHTML;
        
        try {
            if (sendBtn) {
                sendBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Asking...';
                sendBtn.disabled = true;
            }
            
            const response = await fetch('/api/chatgpt/completion', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ prompt })
            });
            
            const result = await response.json();
            
            if (response.ok) {
                // Store the response for later use
                this.lastChatGPTResponse = result.response;
                this.lastChatGPTPrompt = result.prompt;
                
                // Display the response
                responseContainer.innerHTML = `
                    <div class="space-y-3">
                        <div class="bg-gray-800 rounded p-3 border-l-4 border-blue-500">
                            <div class="text-xs text-gray-400 mb-1">Question:</div>
                            <div class="text-gray-200">${this.escapeHtml(result.prompt)}</div>
                        </div>
                        <div class="bg-gray-800 rounded p-3 border-l-4 border-green-500">
                            <div class="text-xs text-gray-400 mb-1">ChatGPT Response:</div>
                            <div class="text-white whitespace-pre-wrap">${this.escapeHtml(result.response)}</div>
                        </div>
                    </div>
                `;
                
                // Clear the input
                input.value = '';
                this.showChatGPTMessage('ChatGPT response received', 'success');
                
                // Auto-hide the success message after 3 seconds
                setTimeout(() => {
                    this.hideChatGPTMessage();
                }, 3000);
                
            } else {
                this.showChatGPTMessage(result.detail || 'Failed to get ChatGPT response', 'error');
            }
            
        } catch (error) {
            console.error('Error asking ChatGPT:', error);
            this.showChatGPTMessage('Failed to get ChatGPT response', 'error');
        } finally {
            if (sendBtn) {
                sendBtn.innerHTML = originalBtnContent;
                sendBtn.disabled = false;
            }
        }
    }
    
    clearChatGPTResponse() {
        const responseContainer = document.getElementById('chatgpt-response');
        const input = document.getElementById('chatgpt-input');
        
        if (responseContainer) {
            responseContainer.innerHTML = `
                <div class="text-gray-500 text-center py-4">
                    <i class="fas fa-comment-dots text-xl mb-2"></i>
                    <p>ChatGPT responses will appear here.</p>
                </div>
            `;
        }
        
        if (input) {
            input.value = '';
        }
        
        this.lastChatGPTResponse = null;
        this.lastChatGPTPrompt = null;
        this.showChatGPTResponseMessage('ChatGPT response cleared', 'success');
    }
    
    async sendChatGPTToContext() {
        if (!this.lastChatGPTResponse) {
            this.showToast('No ChatGPT response to send to context', 'warning');
            return;
        }
        
        try {
            const content = `Question: ${this.lastChatGPTPrompt}\n\nResponse: ${this.lastChatGPTResponse}`;
            
            const response = await fetch('/api/context/add', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    content: content,
                    type: 'chatgpt'
                })
            });
            
            const result = await response.json();
            
            if (response.ok) {
                this.showChatGPTResponseMessage('Added to context', 'success');
                // Reload the context summary
                await this.loadContextSummary();
            } else {
                this.showChatGPTResponseMessage(result.detail || 'Failed to add to context', 'error');
            }
            
        } catch (error) {
            console.error('Error sending ChatGPT to context:', error);
            this.showChatGPTResponseMessage('Failed to add to context', 'error');
        }
    }
    
    async sendDocumentsToContext() {
        if (this.documents.length === 0) {
            this.showToast('No documents to send to context', 'warning');
            return;
        }
        
        try {
            // Create a summary of all uploaded documents
            const documentSummary = this.documents.map(doc => 
                `- ${doc.name} (${this.formatFileSize(doc.size)})`
            ).join('\n');
            
            const content = `Uploaded Documents:\n${documentSummary}\n\nThese documents have been uploaded and are available for reference in the conversation context.`;
            
            const response = await fetch('/api/context/add', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    content: content,
                    type: 'document'
                })
            });
            
            const result = await response.json();
            
            if (response.ok) {
                this.showToast('Documents added to context', 'success');
                // Reload the context summary
                await this.loadContextSummary();
            } else {
                this.showToast(result.detail || 'Failed to add documents to context', 'error');
            }
            
        } catch (error) {
            console.error('Error sending documents to context:', error);
            this.showToast('Failed to add documents to context', 'error');
        }
    }
    
    async loadContextSummary() {
        try {
            const response = await fetch('/api/conversation/summary');
            if (response.ok) {
                const data = await response.json();
                this.updateContextSummary(data.summary);
            }
        } catch (error) {
            console.error('Error loading context summary:', error);
        }
    }
    
    updateDocumentsList() {
        const container = document.getElementById('documents-list');
        if (!container) return;
        
        if (this.documents.length === 0) {
            container.innerHTML = `
                <div class="text-gray-500 text-center py-2 text-sm">
                    No documents uploaded
                </div>
            `;
            return;
        }
        
        container.innerHTML = this.documents.map(doc => `
            <div class="flex items-center justify-between bg-gray-700 rounded p-2">
                <div class="flex-1 min-w-0">
                    <div class="text-sm text-white truncate">${doc.name}</div>
                    <div class="text-xs text-gray-400">${this.formatFileSize(doc.size)}</div>
                </div>
                <button class="text-red-400 hover:text-red-300 ml-2" onclick="dashboard.deleteDocument('${doc.id}')">
                    <i class="fas fa-trash text-sm"></i>
                </button>
            </div>
        `).join('');
    }
    
    escapeHtml(unsafe) {
        return unsafe
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }
    
    showToast(message, type = 'info', duration = 5000) {
        // Use the global app instance if available, otherwise create our own toast
        if (window.app && window.app.showToast) {
            return window.app.showToast(message, type, duration);
        }
        
        // Fallback toast implementation
        const toast = document.createElement('div');
        toast.className = `fixed top-4 right-4 px-4 py-2 rounded shadow-lg z-50 ${
            type === 'success' ? 'bg-green-600 text-white' : 
            type === 'warning' ? 'bg-yellow-600 text-white' :
            type === 'error' ? 'bg-red-600 text-white' : 'bg-blue-600 text-white'
        }`;
        toast.textContent = message;
        
        document.body.appendChild(toast);
        
        setTimeout(() => {
            if (toast.parentElement) {
                toast.remove();
            }
        }, duration);
    }
    
    formatFileSize(bytes) {
        if (window.app && window.app.formatFileSize) {
            return window.app.formatFileSize(bytes);
        }
        
        // Fallback file size formatting
        const sizes = ['B', 'KB', 'MB', 'GB'];
        if (bytes === 0) return '0 B';
        const i = Math.floor(Math.log(bytes) / Math.log(1024));
        return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${sizes[i]}`;
    }
    
    showChatGPTMessage(message, type = 'info') {
        const messageArea = document.getElementById('chatgpt-message-area');
        const messageDiv = document.getElementById('chatgpt-message');
        const messageIcon = document.getElementById('chatgpt-message-icon');
        const messageText = document.getElementById('chatgpt-message-text');
        
        if (!messageArea || !messageDiv || !messageIcon || !messageText) {
            // Fallback to toast if elements not found
            this.showToast(message, type);
            return;
        }
        
        // Set message content
        messageText.textContent = message;
        
        // Set icon and styling based on type
        const styles = {
            success: {
                icon: 'fa-check-circle',
                class: 'bg-green-600 text-white'
            },
            error: {
                icon: 'fa-exclamation-circle',
                class: 'bg-red-600 text-white'
            },
            warning: {
                icon: 'fa-exclamation-triangle', 
                class: 'bg-yellow-600 text-white'
            },
            info: {
                icon: 'fa-info-circle',
                class: 'bg-blue-600 text-white'
            }
        };
        
        const style = styles[type] || styles.info;
        
        // Update icon
        messageIcon.className = `fas ${style.icon} mr-1 text-xs`;
        
        // Update styling with opacity transition
        messageDiv.className = `px-2 py-0.5 rounded text-xs flex items-center opacity-100 transition-opacity duration-200 ${style.class}`;
    }
    
    hideChatGPTMessage() {
        const messageDiv = document.getElementById('chatgpt-message');
        if (messageDiv) {
            // Fade out by changing opacity back to 0
            messageDiv.className = messageDiv.className.replace('opacity-100', 'opacity-0');
        }
    }
    
    showContextMessage(message, type = 'info') {
        const messageArea = document.getElementById('context-summary-message-area');
        const messageDiv = document.getElementById('context-summary-message');
        const messageIcon = document.getElementById('context-summary-message-icon');
        const messageText = document.getElementById('context-summary-message-text');
        
        if (!messageArea || !messageDiv || !messageIcon || !messageText) {
            // Fallback to toast if elements not found
            this.showToast(message, type);
            return;
        }
        
        // Set message content
        messageText.textContent = message;
        
        // Set icon and styling based on type
        const styles = {
            success: {
                icon: 'fa-check-circle',
                class: 'bg-green-600 text-white'
            },
            error: {
                icon: 'fa-exclamation-circle',
                class: 'bg-red-600 text-white'
            },
            warning: {
                icon: 'fa-exclamation-triangle', 
                class: 'bg-yellow-600 text-white'
            },
            info: {
                icon: 'fa-info-circle',
                class: 'bg-blue-600 text-white'
            }
        };
        
        const style = styles[type] || styles.info;
        
        // Update icon
        messageIcon.className = `fas ${style.icon} mr-1 text-xs`;
        
        // Update styling with opacity transition
        messageDiv.className = `px-2 py-0.5 rounded text-xs flex items-center opacity-100 transition-opacity duration-200 ${style.class}`;
        
        // Auto-hide after 3 seconds
        setTimeout(() => this.hideContextMessage(), 3000);
    }
    
    hideContextMessage() {
        const messageDiv = document.getElementById('context-summary-message');
        if (messageDiv) {
            // Fade out by changing opacity back to 0
            messageDiv.className = messageDiv.className.replace('opacity-100', 'opacity-0');
        }
    }
    
    showLiveConversationMessage(message, type = 'info') {
        const messageArea = document.getElementById('live-conversation-message-area');
        const messageDiv = document.getElementById('live-conversation-message');
        const messageIcon = document.getElementById('live-conversation-message-icon');
        const messageText = document.getElementById('live-conversation-message-text');
        
        if (!messageArea || !messageDiv || !messageIcon || !messageText) {
            // Fallback to toast if elements not found
            this.showToast(message, type);
            return;
        }
        
        // Set message content
        messageText.textContent = message;
        
        // Set icon and styling based on type
        const styles = {
            success: {
                icon: 'fa-check-circle',
                class: 'bg-green-600 text-white'
            },
            error: {
                icon: 'fa-exclamation-circle',
                class: 'bg-red-600 text-white'
            },
            warning: {
                icon: 'fa-exclamation-triangle', 
                class: 'bg-yellow-600 text-white'
            },
            info: {
                icon: 'fa-info-circle',
                class: 'bg-blue-600 text-white'
            }
        };
        
        const style = styles[type] || styles.info;
        
        // Update icon
        messageIcon.className = `fas ${style.icon} mr-1 text-xs`;
        
        // Update styling with opacity transition
        messageDiv.className = `px-2 py-0.5 rounded text-xs flex items-center opacity-100 transition-opacity duration-200 ${style.class}`;
        
        // Auto-hide after 3 seconds
        setTimeout(() => this.hideLiveConversationMessage(), 3000);
    }
    
    hideLiveConversationMessage() {
        const messageDiv = document.getElementById('live-conversation-message');
        if (messageDiv) {
            // Fade out by changing opacity back to 0
            messageDiv.className = messageDiv.className.replace('opacity-100', 'opacity-0');
        }
    }
    
    showDiscordVoiceMessage(message, type = 'info') {
        const messageArea = document.getElementById('discord-voice-message-area');
        const messageDiv = document.getElementById('discord-voice-message');
        const messageIcon = document.getElementById('discord-voice-message-icon');
        const messageText = document.getElementById('discord-voice-message-text');
        
        if (!messageArea || !messageDiv || !messageIcon || !messageText) {
            // Fallback to toast if elements not found
            this.showToast(message, type);
            return;
        }
        
        // Set message content
        messageText.textContent = message;
        
        // Set icon and styling based on type
        const styles = {
            success: {
                icon: 'fa-check-circle',
                class: 'bg-green-600 text-white'
            },
            error: {
                icon: 'fa-exclamation-circle',
                class: 'bg-red-600 text-white'
            },
            warning: {
                icon: 'fa-exclamation-triangle', 
                class: 'bg-yellow-600 text-white'
            },
            info: {
                icon: 'fa-info-circle',
                class: 'bg-blue-600 text-white'
            }
        };
        
        const style = styles[type] || styles.info;
        
        // Update icon
        messageIcon.className = `fas ${style.icon} mr-1 text-xs`;
        
        // Update styling with opacity transition
        messageDiv.className = `px-2 py-0.5 rounded text-xs flex items-center opacity-100 transition-opacity duration-200 ${style.class}`;
        
        // Auto-hide after 3 seconds
        setTimeout(() => this.hideDiscordVoiceMessage(), 3000);
    }
    
    hideDiscordVoiceMessage() {
        const messageDiv = document.getElementById('discord-voice-message');
        if (messageDiv) {
            // Fade out by changing opacity back to 0
            messageDiv.className = messageDiv.className.replace('opacity-100', 'opacity-0');
        }
    }
    
    showAIModeMessage(message, type = 'info') {
        const messageArea = document.getElementById('ai-mode-message-area');
        const messageDiv = document.getElementById('ai-mode-message');
        const messageIcon = document.getElementById('ai-mode-message-icon');
        const messageText = document.getElementById('ai-mode-message-text');
        
        if (!messageArea || !messageDiv || !messageIcon || !messageText) {
            // Fallback to toast if elements not found
            this.showToast(message, type);
            return;
        }
        
        // Set message content
        messageText.textContent = message;
        
        // Set icon and styling based on type
        const styles = {
            success: {
                icon: 'fa-check-circle',
                class: 'bg-green-600 text-white'
            },
            error: {
                icon: 'fa-exclamation-circle',
                class: 'bg-red-600 text-white'
            },
            warning: {
                icon: 'fa-exclamation-triangle', 
                class: 'bg-yellow-600 text-white'
            },
            info: {
                icon: 'fa-info-circle',
                class: 'bg-blue-600 text-white'
            }
        };
        
        const style = styles[type] || styles.info;
        
        // Update icon
        messageIcon.className = `fas ${style.icon} mr-1 text-xs`;
        
        // Update styling with opacity transition
        messageDiv.className = `px-2 py-0.5 rounded text-xs flex items-center opacity-100 transition-opacity duration-200 ${style.class}`;
        
        // Auto-hide after 3 seconds
        setTimeout(() => this.hideAIModeMessage(), 3000);
    }
    
    hideAIModeMessage() {
        const messageDiv = document.getElementById('ai-mode-message');
        if (messageDiv) {
            // Fade out by changing opacity back to 0
            messageDiv.className = messageDiv.className.replace('opacity-100', 'opacity-0');
        }
    }
    
    showModelSelectionMessage(message, type = 'info') {
        const messageArea = document.getElementById('model-selection-message-area');
        const messageDiv = document.getElementById('model-selection-message');
        const messageIcon = document.getElementById('model-selection-message-icon');
        const messageText = document.getElementById('model-selection-message-text');
        
        if (!messageArea || !messageDiv || !messageIcon || !messageText) {
            // Fallback to toast if elements not found
            this.showToast(message, type);
            return;
        }
        
        // Set message content
        messageText.textContent = message;
        
        // Set icon and styling based on type
        const styles = {
            success: {
                icon: 'fa-check-circle',
                class: 'bg-green-600 text-white'
            },
            error: {
                icon: 'fa-exclamation-circle',
                class: 'bg-red-600 text-white'
            },
            warning: {
                icon: 'fa-exclamation-triangle', 
                class: 'bg-yellow-600 text-white'
            },
            info: {
                icon: 'fa-info-circle',
                class: 'bg-blue-600 text-white'
            }
        };
        
        const style = styles[type] || styles.info;
        
        // Update icon
        messageIcon.className = `fas ${style.icon} mr-1 text-xs`;
        
        // Update styling with opacity transition
        messageDiv.className = `px-2 py-0.5 rounded text-xs flex items-center opacity-100 transition-opacity duration-200 ${style.class}`;
        
        // Auto-hide after 3 seconds
        setTimeout(() => this.hideModelSelectionMessage(), 3000);
    }
    
    hideModelSelectionMessage() {
        const messageDiv = document.getElementById('model-selection-message');
        if (messageDiv) {
            // Fade out by changing opacity back to 0
            messageDiv.className = messageDiv.className.replace('opacity-100', 'opacity-0');
        }
    }
    
    showDocumentsMessage(message, type = 'info') {
        const messageArea = document.getElementById('documents-message-area');
        const messageDiv = document.getElementById('documents-message');
        const messageIcon = document.getElementById('documents-message-icon');
        const messageText = document.getElementById('documents-message-text');
        
        if (!messageArea || !messageDiv || !messageIcon || !messageText) {
            // Fallback to toast if elements not found
            this.showToast(message, type);
            return;
        }
        
        // Set message content
        messageText.textContent = message;
        
        // Set icon and styling based on type
        const styles = {
            success: {
                icon: 'fa-check-circle',
                class: 'bg-green-600 text-white'
            },
            error: {
                icon: 'fa-exclamation-circle',
                class: 'bg-red-600 text-white'
            },
            warning: {
                icon: 'fa-exclamation-triangle', 
                class: 'bg-yellow-600 text-white'
            },
            info: {
                icon: 'fa-info-circle',
                class: 'bg-blue-600 text-white'
            }
        };
        
        const style = styles[type] || styles.info;
        
        // Update icon
        messageIcon.className = `fas ${style.icon} mr-1 text-xs`;
        
        // Update styling with opacity transition
        messageDiv.className = `px-2 py-0.5 rounded text-xs flex items-center opacity-100 transition-opacity duration-200 ${style.class}`;
        
        // Auto-hide after 3 seconds
        setTimeout(() => this.hideDocumentsMessage(), 3000);
    }
    
    hideDocumentsMessage() {
        const messageDiv = document.getElementById('documents-message');
        if (messageDiv) {
            // Fade out by changing opacity back to 0
            messageDiv.className = messageDiv.className.replace('opacity-100', 'opacity-0');
        }
    }
    
    showSessionSpendMessage(message, type = 'info') {
        const messageArea = document.getElementById('session-spend-message-area');
        const messageDiv = document.getElementById('session-spend-message');
        const messageIcon = document.getElementById('session-spend-message-icon');
        const messageText = document.getElementById('session-spend-message-text');
        
        if (!messageArea || !messageDiv || !messageIcon || !messageText) {
            // Fallback to toast if elements not found
            this.showToast(message, type);
            return;
        }
        
        // Set message content
        messageText.textContent = message;
        
        // Set icon and styling based on type
        const styles = {
            success: {
                icon: 'fa-check-circle',
                class: 'bg-green-600 text-white'
            },
            error: {
                icon: 'fa-exclamation-circle',
                class: 'bg-red-600 text-white'
            },
            warning: {
                icon: 'fa-exclamation-triangle', 
                class: 'bg-yellow-600 text-white'
            },
            info: {
                icon: 'fa-info-circle',
                class: 'bg-blue-600 text-white'
            }
        };
        
        const style = styles[type] || styles.info;
        
        // Update icon
        messageIcon.className = `fas ${style.icon} mr-1 text-xs`;
        
        // Update styling with opacity transition
        messageDiv.className = `px-2 py-0.5 rounded text-xs flex items-center opacity-100 transition-opacity duration-200 ${style.class}`;
        
        // Auto-hide after 3 seconds
        setTimeout(() => this.hideSessionSpendMessage(), 3000);
    }
    
    hideSessionSpendMessage() {
        const messageDiv = document.getElementById('session-spend-message');
        if (messageDiv) {
            // Fade out by changing opacity back to 0
            messageDiv.className = messageDiv.className.replace('opacity-100', 'opacity-0');
        }
    }
    
    showChatGPTResponseMessage(message, type = 'info') {
        const messageArea = document.getElementById('chatgpt-response-message-area');
        const messageDiv = document.getElementById('chatgpt-response-message');
        const messageIcon = document.getElementById('chatgpt-response-message-icon');
        const messageText = document.getElementById('chatgpt-response-message-text');
        
        if (!messageArea || !messageDiv || !messageIcon || !messageText) {
            // Fallback to toast if elements not found
            this.showToast(message, type);
            return;
        }
        
        // Set message content
        messageText.textContent = message;
        
        // Set icon and styling based on type
        const styles = {
            success: {
                icon: 'fa-check-circle',
                class: 'bg-green-600 text-white'
            },
            error: {
                icon: 'fa-exclamation-circle',
                class: 'bg-red-600 text-white'
            },
            warning: {
                icon: 'fa-exclamation-triangle', 
                class: 'bg-yellow-600 text-white'
            },
            info: {
                icon: 'fa-info-circle',
                class: 'bg-blue-600 text-white'
            }
        };
        
        const style = styles[type] || styles.info;
        
        // Update icon
        messageIcon.className = `fas ${style.icon} mr-1 text-xs`;
        
        // Update styling with opacity transition
        messageDiv.className = `px-2 py-0.5 rounded text-xs flex items-center opacity-100 transition-opacity duration-200 ${style.class}`;
        
        // Auto-hide after 3 seconds
        setTimeout(() => this.hideChatGPTResponseMessage(), 3000);
    }
    
    hideChatGPTResponseMessage() {
        const messageDiv = document.getElementById('chatgpt-response-message');
        if (messageDiv) {
            // Fade out by changing opacity back to 0
            messageDiv.className = messageDiv.className.replace('opacity-100', 'opacity-0');
        }
    }
    
    async exportTranscript() {
        try {
            const response = await fetch('/api/export/transcript', {
                method: 'POST'
            });
            
            const result = await response.json();
            
            if (response.ok) {
                this.showLiveConversationMessage(`Exported ${result.turns_count} turns to ${result.filename}`, 'success');
            } else {
                this.showLiveConversationMessage(result.detail || 'Failed to export transcript', 'error');
            }
            
        } catch (error) {
            console.error('Error exporting transcript:', error);
            this.showLiveConversationMessage('Failed to export transcript', 'error');
        }
    }
    
    async exportContext() {
        try {
            const response = await fetch('/api/export/context', {
                method: 'POST'
            });
            
            const result = await response.json();
            
            if (response.ok) {
                this.showContextMessage('Context exported', 'success');
            } else {
                this.showContextMessage(result.detail || 'Failed to export context', 'error');
            }
            
        } catch (error) {
            console.error('Error exporting context:', error);
            this.showContextMessage('Failed to export context', 'error');
        }
    }
    
    async loadSessionStatus() {
        try {
            const response = await fetch('/api/session/status');
            if (response.ok) {
                const status = await response.json();
                this.updateSessionUI(status);
            }
        } catch (error) {
            console.error('Error loading session status:', error);
        }
    }
    
    async startSession() {
        const startBtn = document.getElementById('session-start');
        const stopBtn = document.getElementById('session-stop');
        const statusDiv = document.getElementById('session-status');
        
        try {
            startBtn.disabled = true;
            
            const response = await fetch('/api/session/start', {
                method: 'POST'
            });
            
            const result = await response.json();
            
            if (response.ok) {
                stopBtn.disabled = false;
                statusDiv.textContent = `Session started at ${new Date().toLocaleTimeString()}`;
                statusDiv.className = 'text-xs text-green-400';
                this.showSessionSpendMessage('Session tracking started', 'success');
                
                // Update session timer
                this.startSessionTimer(result.start_time);
            } else {
                this.showSessionSpendMessage(result.detail || 'Failed to start session', 'error');
                startBtn.disabled = false;
            }
            
        } catch (error) {
            console.error('Error starting session:', error);
            this.showSessionSpendMessage('Failed to start session', 'error');
            startBtn.disabled = false;
        }
    }
    
    async stopSession() {
        const startBtn = document.getElementById('session-start');
        const stopBtn = document.getElementById('session-stop');
        const statusDiv = document.getElementById('session-status');
        const summaryDiv = document.getElementById('session-summary');
        
        try {
            stopBtn.disabled = true;
            statusDiv.textContent = 'Calculating costs...';
            statusDiv.className = 'text-xs text-yellow-400';
            
            const response = await fetch('/api/session/stop', {
                method: 'POST'
            });
            
            const result = await response.json();
            
            if (response.ok) {
                // Update UI with results
                startBtn.disabled = false;
                statusDiv.textContent = 'Ready to start new session';
                statusDiv.className = 'text-xs text-gray-400';
                
                // Show enhanced session summary with split-stack costs
                const costDiv = document.getElementById('session-cost');
                
                if (costDiv) {
                    costDiv.textContent = `$${result.total_usd.toFixed(4)}`;
                }
                
                // Update enhanced cost breakdown elements
                this.updateSessionCostBreakdown(result);
                
                summaryDiv.classList.remove('hidden');
                
                this.showSessionSpendMessage(`Session completed: $${result.total_usd.toFixed(4)}`, 'success');
                
                // Clear session timer
                if (this.sessionTimer) {
                    clearInterval(this.sessionTimer);
                }
                
            } else {
                this.showSessionSpendMessage(result.detail || 'Failed to stop session', 'error');
                stopBtn.disabled = false;
                statusDiv.textContent = 'Session running...';
                statusDiv.className = 'text-xs text-green-400';
            }
            
        } catch (error) {
            console.error('Error stopping session:', error);
            this.showSessionSpendMessage('Failed to stop session', 'error');
            stopBtn.disabled = false;
        }
    }
    
    updateSessionCostBreakdown(result) {
        const sttCostEl = document.getElementById('session-stt-cost');
        const ttsCostEl = document.getElementById('session-tts-cost');
        const tokenCostEl = document.getElementById('session-token-cost');
        const sttMinutesEl = document.getElementById('session-stt-minutes');
        const ttsMinutesEl = document.getElementById('session-tts-minutes');
        const totalTokensEl = document.getElementById('session-total-tokens');
        const requestsEl = document.getElementById('session-requests');
        const sttProviderEl = document.getElementById('session-stt-provider');
        const ttsProviderEl = document.getElementById('session-tts-provider');
        const reasoningModelEl = document.getElementById('session-reasoning-model');

        if (result.breakdown && Array.isArray(result.breakdown)) {
            let sttCost = 0, ttsCost = 0, tokenCost = 0;
            let sttMinutes = 0, ttsDetail = '', totalTokens = 0, totalRequests = 0;
            let sttProvider = 'OpenAI', ttsProvider = 'OpenAI', reasoningModel = 'GPT-5.4';

            result.breakdown.forEach(item => {
                if (item.service === 'Speech-to-Text') {
                    sttCost += item.cost_usd || 0;
                    sttMinutes += item.minutes || 0;
                    if (item.provider) sttProvider = item.provider;
                } else if (item.service === 'Text-to-Speech') {
                    ttsCost += item.cost_usd || 0;
                    if (item.provider) ttsProvider = item.provider;
                    if (item.characters) {
                        ttsDetail = `${(item.characters || 0).toLocaleString()} chars`;
                    } else {
                        ttsDetail = `${(item.minutes || 0).toFixed(1)} min`;
                    }
                } else if (item.service === 'Text Processing') {
                    tokenCost += item.cost_usd || 0;
                    totalTokens += (item.input_tokens || 0) + (item.output_tokens || 0);
                    totalRequests += item.requests || 0;
                    if (item.model) reasoningModel = item.model;
                }
            });

            if (sttCostEl) sttCostEl.textContent = `$${sttCost.toFixed(3)}`;
            if (ttsCostEl) ttsCostEl.textContent = `$${ttsCost.toFixed(3)}`;
            if (tokenCostEl) tokenCostEl.textContent = `$${tokenCost.toFixed(3)}`;
            if (sttMinutesEl) sttMinutesEl.textContent = `${sttMinutes.toFixed(1)} min`;
            if (ttsMinutesEl) ttsMinutesEl.textContent = ttsDetail || '0.0 min';
            if (totalTokensEl) totalTokensEl.textContent = totalTokens.toLocaleString();
            if (requestsEl) requestsEl.textContent = totalRequests.toString();
            if (sttProviderEl) sttProviderEl.textContent = sttProvider;
            if (ttsProviderEl) ttsProviderEl.textContent = ttsProvider;
            if (reasoningModelEl) reasoningModelEl.textContent = reasoningModel;

        } else if (result.cost_summary) {
            const summary = result.cost_summary;
            if (sttMinutesEl) sttMinutesEl.textContent = `${(summary.stt_minutes || 0).toFixed(1)} min`;
            if (ttsMinutesEl) ttsMinutesEl.textContent = `${(summary.tts_minutes || 0).toFixed(1)} min`;
            if (totalTokensEl) totalTokensEl.textContent = (summary.total_tokens || 0).toLocaleString();
            if (requestsEl) requestsEl.textContent = (summary.total_requests || 0).toString();

            const estimatedSTTCost = (summary.stt_minutes || 0) * 0.006;
            const estimatedTTSCost = (summary.tts_minutes || 0) * 0.015;
            const estimatedTokenCost = result.total_usd - estimatedSTTCost - estimatedTTSCost;

            if (sttCostEl) sttCostEl.textContent = `$${estimatedSTTCost.toFixed(3)}`;
            if (ttsCostEl) ttsCostEl.textContent = `$${estimatedTTSCost.toFixed(3)}`;
            if (tokenCostEl) tokenCostEl.textContent = `$${Math.max(0, estimatedTokenCost).toFixed(3)}`;
        }
    }
    
    startSessionTimer(startTime) {
        const statusDiv = document.getElementById('session-status');
        
        this.sessionTimer = setInterval(() => {
            const elapsed = Math.floor(Date.now() / 1000) - startTime;
            const minutes = Math.floor(elapsed / 60);
            const seconds = elapsed % 60;
            statusDiv.textContent = `Session running: ${minutes}:${seconds.toString().padStart(2, '0')}`;
        }, 1000);
    }
    
    updateSessionUI(status) {
        const startBtn = document.getElementById('session-start');
        const stopBtn = document.getElementById('session-stop');
        const statusDiv = document.getElementById('session-status');
        
        if (status.running) {
            startBtn.disabled = true;
            stopBtn.disabled = false;
            this.startSessionTimer(status.start_time);
        } else {
            startBtn.disabled = false;
            stopBtn.disabled = true;
            statusDiv.textContent = 'Ready to start session tracking';
            statusDiv.className = 'text-xs text-gray-400';
        }
    }
    
    cleanup() {
        this.stopTranscriptPolling();
        this.stopStatusPolling();
        if (this.sessionTimer) {
            clearInterval(this.sessionTimer);
        }
    }
}

// Initialize dashboard when DOM is ready
let dashboard;

document.addEventListener('DOMContentLoaded', () => {
    dashboard = new Dashboard();
});

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (dashboard) {
        dashboard.cleanup();
    }
});

// Export for use in HTML
window.dashboard = dashboard;
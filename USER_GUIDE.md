# Discord AI Co-Host Bot - User Guide

## Overview

The Discord AI Co-Host Bot is a sophisticated AI assistant designed to participate in Discord voice conversations. It listens to conversations, builds context, and can actively participate when requested. The web interface provides comprehensive control and monitoring capabilities.

## Getting Started

1. **Access the Web Interface**: Navigate to `http://localhost:8000` in your browser
2. **Check Status**: The top navigation bar shows real-time connection status for Discord, OpenAI, and Voice services
3. **Review Logs**: Visit the Logs & Errors page to monitor system health and troubleshoot issues

## Web Interface Pages

### 1. Dashboard (`/`)
Main control interface for managing the AI co-host.

### 2. Logs & Errors (`/logs`)  
Comprehensive logging interface with interactive filtering and analysis tools.

## Dashboard Features

### Control Panel (Left Side)

#### Voice Channel Controls
- **Channel Selection**: Dropdown menu shows all available Discord voice channels across your servers
- **Join Button** (🔗): Connect the AI to the selected voice channel
- **Leave Button** (🔚): Disconnect from the current voice channel
- **Status**: Shows current connection status and channel name

#### AI Mode Toggle
- **Passive Mode**: AI listens and builds context without speaking
- **Active Mode**: AI can actively participate in conversations
- **Toggle Button**: Switch between modes
- **Force AI Response**: Manually trigger an AI response regardless of mode

#### ChatGPT Integration
- **Text Input**: Ask ChatGPT questions directly through the web interface
- **Send Button**: Submit your question to ChatGPT
- **Keyboard Shortcut**: Use Ctrl+Enter to send questions quickly
- **Response Display**: View ChatGPT responses in a formatted interface

#### Document Management
- **Upload Area**: Drag and drop or click to upload PDF, DOCX, TXT, or MD files
- **Document List**: View uploaded documents with file names and sizes
- **Delete Documents**: Remove individual documents with the trash icon
- **Send to Context**: Add document summaries to the AI's context knowledge

### Main Content Area (Right Side)

#### Live Conversation
- **Real-time Transcript**: Shows ongoing voice conversation transcripts
- **Auto-scroll**: Automatically scrolls to show latest messages
- **Refresh Button**: Manually refresh the transcript
- **Speaker Attribution**: Shows who said what in the conversation

#### ChatGPT Response Window
- **Question & Answer Display**: Shows your ChatGPT queries and responses in an organized format
- **Clear Button**: Remove all ChatGPT responses from the display
- **Send to Context**: Add ChatGPT responses to the AI's context knowledge
- **Scrollable**: Handle long responses with overflow scrolling

#### Context Summary
- **AI Context**: Shows the accumulated knowledge and context the AI has built
- **Generate Button**: Create or update the context summary from recent conversations
- **Auto-update**: Context updates when you add ChatGPT responses or documents
- **Formatted Display**: Clean, readable formatting for complex context information

## Application Flow & Logic

### 1. Initial Setup
1. Start the application with `docker-compose up`
2. The AI connects to Discord and OpenAI services automatically
3. Web interface becomes available at `localhost:8000`
4. Status indicators show connection health

### 2. Joining a Voice Channel
1. Select a Discord voice channel from the dropdown
2. Click the Join button to connect
3. AI begins listening in Passive mode
4. Live transcript starts showing conversation

### 3. Building Context
The AI builds context through multiple sources:
- **Voice Conversations**: Automatically transcribed and analyzed
- **ChatGPT Interactions**: Manual Q&A sessions added to context
- **Document Uploads**: File content summaries integrated into knowledge base
- **Context Summary**: Generated summaries of accumulated information

### 4. AI Participation Modes

#### Passive Mode (Default)
- AI listens to all conversation
- Builds context and understanding
- Does not speak or interrupt
- Perfect for learning about ongoing topics

#### Active Mode
- AI can actively participate in conversations
- Uses built context to provide relevant responses
- Responds when appropriate based on conversation flow
- Can be manually triggered with "Force AI Response"

### 5. ChatGPT Integration Workflow
1. Type questions in the "Ask ChatGPT" text area
2. Receive responses in the dedicated ChatGPT Response window
3. **Clear**: Remove responses to start fresh
4. **Send to Context**: Add valuable responses to AI's knowledge base
5. Context-enhanced responses improve AI voice participation

### 6. Document Processing Workflow
1. Upload documents (PDF, DOCX, TXT, MD) via drag-and-drop or file selection
2. Documents appear in the inline list with file information
3. Delete unwanted documents individually
4. **Send to Context**: Process all uploaded documents and add summaries to AI context
5. AI can reference document content in voice conversations

## Feature Testing Guide

### Test 1: Basic Voice Connection
- [ ] Select a Discord voice channel
- [ ] Click Join - verify connection success message
- [ ] Check that voice status shows "Connected to [Channel Name]"
- [ ] Speak in Discord - verify transcript appears in Live Conversation
- [ ] Click Leave - verify disconnection

### Test 2: AI Mode Switching
- [ ] Verify starts in Passive mode
- [ ] Click "Activate" - verify mode changes to Active
- [ ] Check mode description updates appropriately
- [ ] Toggle back to Passive mode

### Test 3: ChatGPT Integration
- [ ] Enter a question in the "Ask ChatGPT" text area
- [ ] Click "Ask ChatGPT" - verify loading state
- [ ] Verify response appears in ChatGPT Response window
- [ ] Test "Clear" button - verify response is removed
- [ ] Ask another question and test "Send to Context"
- [ ] Verify context summary updates with ChatGPT content

### Test 4: Document Management
- [ ] Upload a test document (PDF/DOCX/TXT/MD)
- [ ] Verify document appears in the document list
- [ ] Test delete functionality with trash icon
- [ ] Upload multiple documents
- [ ] Click "Send to Context" - verify context summary includes document information

### Test 5: Context System Integration
- [ ] Generate conversation context with "Generate" button
- [ ] Add ChatGPT responses to context
- [ ] Add documents to context
- [ ] Verify context summary combines all sources appropriately
- [ ] Test how context affects AI voice responses in Active mode

### Test 6: Logs and Monitoring
- [ ] Visit Logs & Errors page (`/logs`)
- [ ] Verify logs display properly (should show 49+ entries)
- [ ] Test stat box filtering (click Error, Warning, Info, Debug, Total)
- [ ] Test component and search filters
- [ ] Verify log entries display on separate lines
- [ ] Test auto-refresh functionality

## Expected Behavior

### Status Indicators
- **Green**: Service connected and healthy
- **Red**: Service disconnected or error
- **Yellow**: Warning or partial functionality

### Response Times
- **ChatGPT**: 2-10 seconds depending on query complexity
- **Voice Transcription**: Real-time with minimal delay
- **Context Generation**: 5-15 seconds for comprehensive summaries

### Error Handling
- Connection failures show clear error messages
- Invalid file uploads are rejected with explanatory messages
- API errors display user-friendly notifications
- Auto-retry mechanisms for temporary failures

## Troubleshooting Common Issues

### 1. Discord Connection Issues
- Verify bot has permissions in target Discord server
- Check that Discord bot token is valid in environment variables
- Ensure voice channel is accessible and not full

### 2. OpenAI API Issues
- Verify API key is set correctly
- Check API usage quotas and billing
- Monitor rate limiting in logs

### 3. ChatGPT Not Responding
- Check OpenAI API connection status
- Verify network connectivity
- Review error logs for specific error messages

### 4. Document Upload Failures
- Ensure file types are supported (PDF, DOCX, TXT, MD)
- Check file size limits (typically 50MB)
- Verify sufficient disk space

### 5. Context Not Updating
- Try manually refreshing context with "Generate" button
- Check that OpenAI API is responding
- Verify content was successfully sent to context

## Advanced Usage Tips

### 1. Context Management Strategy
- Use ChatGPT to research topics before voice conversations
- Upload relevant documents before starting discussions
- Regularly generate context summaries to consolidate information
- Clear and rebuild context for different conversation topics

### 2. Optimal AI Participation
- Start in Passive mode to build context
- Switch to Active mode once AI has sufficient background
- Use "Force AI Response" for specific questions or prompts
- Monitor Live Conversation to ensure AI responses are appropriate

### 3. Document Strategy
- Upload key reference materials before conversations
- Use descriptive filenames for easier document management
- Send documents to context before switching to Active mode
- Remove outdated documents to keep context focused

### 4. Monitoring and Maintenance
- Regularly check Logs & Errors for system health
- Monitor API usage and quotas
- Clear ChatGPT responses periodically to avoid clutter
- Restart services if connection issues persist

## API Endpoints (For Advanced Users)

- `GET /api/status` - System status information
- `POST /api/chatgpt/completion` - Get ChatGPT text completion
- `POST /api/context/add` - Add content to context summary
- `GET /api/logs` - Retrieve application logs
- `GET /api/conversation/transcript` - Get conversation transcript
- `POST /api/conversation/summarize` - Generate context summary

This comprehensive guide should help you effectively use and test all features of the Discord AI Co-Host Bot. Report any issues or unexpected behavior for further refinement.
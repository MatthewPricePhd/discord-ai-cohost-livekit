# Discord AI Co-Host Bot

An intelligent AI-powered podcast co-host that joins Discord voice channels to enhance live podcast recordings using GPT-5 Realtime API.

## Features

- **Real-time Voice Interaction**: Uses OpenAI GPT-5 Realtime API for natural voice conversations
- **Discord Integration**: Joins voice channels as a participant, not just a bot
- **Intelligent Context Management**: Maintains conversation context and integrates uploaded research materials  
- **Web Dashboard**: Real-time control interface for podcast hosts
- **Document Processing**: Upload PDFs, DOCX, and other documents for AI context enhancement
- **Passive/Active Modes**: Listen quietly or actively participate on demand
- **Context-Aware Responses**: References conversation history and research materials

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Discord Bot Token ([Create a Discord App](https://discord.com/developers/applications))
- OpenAI API Key with GPT-5 Realtime API access

### 1. Clone and Setup

```bash
git clone <repository-url>
cd discord-ai-cohost

# Copy environment template
cp .env.example .env

# Edit .env with your credentials
nano .env
```

### 2. Required Environment Variables

Edit `.env` file:

```env
# Required
DISCORD_BOT_TOKEN=your_discord_bot_token_here
OPENAI_API_KEY=your_openai_api_key_here
SECRET_KEY=your_secret_key_here
```

### 3. Run with Docker

```bash
# Start the application
docker-compose up -d

# View logs
docker-compose logs -f ai-cohost

# Stop the application
docker-compose down
```

The web dashboard will be available at `http://localhost:8000`

## Usage

### 1. Invite Bot to Discord

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications)
2. Select your application
3. Go to OAuth2 > URL Generator
4. Select scopes: `bot`
5. Select permissions: `Connect`, `Speak`, `Use Voice Activity`, `Read Message History`, `Send Messages`
6. Use the generated URL to invite the bot to your server

### 2. Start a Podcast Session

1. Join a voice channel in Discord
2. Open the web dashboard at `http://localhost:8000`
3. Select your voice channel from the dropdown
4. Click "Join" to connect the AI co-host
5. Upload any research documents (optional)
6. The bot starts in "Passive" mode, listening and building context

### 3. Activate the AI Co-Host

- Click "Activate" in the web dashboard to switch to active mode
- The AI will respond to conversations naturally
- Click "Force AI Response" to make it speak immediately
- Switch back to "Passive" mode to return to listening-only

### 4. Monitor and Control

- View live conversation transcripts in the dashboard
- See AI-generated context summaries
- Monitor connection status and audio quality
- Upload documents during the session for additional context

## Development

### Development Environment

```bash
# Start development environment with hot reloading
docker-compose -f docker-compose.dev.yml up -d

# View development logs
docker-compose -f docker-compose.dev.yml logs -f ai-cohost-dev

# Access development tools (Redis admin, etc.)
docker-compose -f docker-compose.dev.yml --profile admin up -d
```

Development dashboard: `http://localhost:8000`
Redis Commander (if enabled): `http://localhost:8081`

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env

# Run locally
python -m src.main
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DISCORD_BOT_TOKEN` | Required | Discord bot token |
| `OPENAI_API_KEY` | Required | OpenAI API key |
| `SECRET_KEY` | Required | Web app secret key |
| `WEB_PORT` | 8000 | Web server port |
| `MAX_FILE_SIZE` | 50MB | Maximum upload file size |
| `SUPPORTED_FORMATS` | pdf,docx,txt,md | Supported document formats |
| `MAX_CONTEXT_TOKENS` | 128000 | GPT-5 context window limit |
| `LOG_LEVEL` | INFO | Logging level |

### Discord Permissions

The bot requires these Discord permissions:
- Connect (to join voice channels)
- Speak (to output audio)
- Use Voice Activity (for voice detection)
- Read Message History
- Send Messages
- Use Slash Commands

## Architecture

### Components

- **Discord Client**: Manages voice channel connections and audio streaming
- **OpenAI Realtime API**: Handles real-time voice processing with GPT-5
- **Web Interface**: FastAPI-based dashboard for host controls
- **Document Processor**: Extracts and chunks uploaded documents
- **Vector Store**: ChromaDB for semantic document search
- **Context Manager**: Intelligent context window management

### Audio Pipeline

```
Discord Voice → Audio Processing → OpenAI Realtime API → AI Response → Discord Voice
```

### Context Flow

```
Conversation → Summarization → Topic Extraction → Document Retrieval → Context Window → AI Response
```

## API Documentation

When running in development mode, API documentation is available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### Key Endpoints

- `GET /api/status` - Get application status
- `POST /api/voice/join` - Join voice channel
- `POST /api/mode/toggle` - Toggle passive/active mode
- `POST /api/documents/upload` - Upload documents
- `GET /api/conversation/transcript` - Get conversation transcript

## Deployment

### Production Deployment

1. Set up a VPS or cloud instance
2. Install Docker and Docker Compose
3. Clone the repository and configure `.env`
4. Use the production docker-compose configuration:

```bash
# Start with Nginx reverse proxy
docker-compose --profile production up -d

# Or simple deployment without Nginx
docker-compose up -d
```

### SSL/HTTPS Setup

1. Obtain SSL certificates (Let's Encrypt recommended)
2. Update `nginx.conf` with your domain and certificate paths
3. Start with production profile:

```bash
docker-compose --profile production up -d
```

### Scaling Considerations

- Use Redis for session management across multiple instances
- Configure load balancing for multiple bot instances
- Monitor resource usage (CPU, memory, API costs)
- Set up logging aggregation for production monitoring

## Cost Estimation

### OpenAI API Costs (Approximate)

- **GPT-5 Realtime API**: ~$0.06-0.12 per minute of active conversation
- **Text Embeddings**: ~$0.10 per 1M tokens for document processing
- **Chat Completions**: ~$0.03 per 1K tokens for summarization

**Estimated cost for 60-minute podcast**: $5-10 (mostly realtime API usage)

### Resource Requirements

- **Memory**: 1-2 GB RAM minimum
- **CPU**: 2 cores recommended
- **Storage**: 10 GB for documents and logs
- **Network**: Stable internet with low latency to Discord and OpenAI

## Troubleshooting

### Common Issues

1. **Bot won't join voice channel**
   - Check Discord permissions
   - Verify bot token
   - Ensure bot is in the same server as the voice channel

2. **OpenAI API errors**
   - Verify API key has GPT-5 Realtime API access
   - Check API usage limits and billing
   - Monitor rate limits

3. **Audio quality issues**
   - Check network latency
   - Verify audio format compatibility
   - Monitor CPU usage during sessions

4. **Document upload failures**
   - Check file size limits
   - Verify supported file formats
   - Ensure sufficient disk space

### Debug Mode

Enable debug logging:

```env
LOG_LEVEL=DEBUG
DEBUG=true
```

View detailed logs:

```bash
docker-compose logs -f ai-cohost
```

### Health Monitoring

- Health check endpoint: `http://localhost:8000/health`
- Connection status in web dashboard
- Monitor Docker container health: `docker-compose ps`

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

### Development Guidelines

- Follow PEP 8 for Python code
- Use type hints
- Add docstrings for functions
- Update documentation for new features
- Test thoroughly before submitting

## License

[Add your license information here]

## Support

- Create an issue for bugs or feature requests
- Check the troubleshooting section for common problems
- Review logs for error details

## Roadmap

- [ ] Multi-language support
- [ ] Custom voice training
- [ ] Twitch/YouTube chat integration
- [ ] Advanced analytics dashboard
- [ ] Plugin system for extensions
- [ ] Mobile app for remote control
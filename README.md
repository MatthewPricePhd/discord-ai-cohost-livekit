# Discord AI Co-Host Bot

An intelligent AI-powered podcast co-host that joins Discord voice channels to enhance live podcast recordings. Supports OpenAI gpt-realtime (GA), ElevenLabs, and GPT-5.4 for a modern, cost-efficient voice AI pipeline.

## Features

- **Real-time Voice Interaction**: OpenAI gpt-realtime (GA) with gpt-realtime-mini for cost-efficient passive mode
- **Multi-Provider TTS/STT**: Hot-swap between OpenAI and ElevenLabs (Flash v2.5, Scribe v2) from the dashboard
- **ML-Based Voice Detection**: Silero VAD replaces amplitude-based detection for reliable speech detection
- **GPT-5.4 Reasoning**: 1M token context window with gpt-5.3-instant for cost-efficient background tasks
- **Observer Agent**: Background conversation analysis — talking points, fact-checks, and topic suggestions surfaced to the dashboard
- **Discord Integration**: Joins voice channels as a participant, not just a bot
- **Intelligent Context Management**: Progressive summarization, topic extraction, document RAG, and key-point notes
- **Web Dashboard**: Real-time controls with provider/voice/model selectors, cost tracking, and AI insights panel
- **Document Processing**: Upload PDFs, DOCX, and other documents for AI context enhancement
- **Split-Stack Architecture**: Passive Listening, Speech-to-Speech, and Ask ChatGPT modes

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Discord Bot Token ([Create a Discord App](https://discord.com/developers/applications))
- OpenAI API Key with Realtime API access
- OpenAI Admin Key (optional, for Usage API cost tracking)
- ElevenLabs API Key (optional, for ElevenLabs TTS/STT)

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

# Optional — for Usage API cost tracking
OPENAI_ADMIN_KEY=your_openai_admin_key_here

# Optional — enables ElevenLabs as TTS/STT provider
ELEVENLABS_API_KEY=your_elevenlabs_api_key_here

# Provider selection (openai or elevenlabs)
TTS_PROVIDER=openai
STT_PROVIDER=openai

# Model selection
OPENAI_REALTIME_MODEL=gpt-realtime
OPENAI_REASONING_MODEL=gpt-5.4
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
| `OPENAI_ADMIN_KEY` | Optional | OpenAI Admin key for Usage API cost tracking |
| `SECRET_KEY` | Required | Web app secret key |
| `OPENAI_REALTIME_MODEL` | gpt-realtime | Realtime voice model (`gpt-realtime` or `gpt-realtime-mini`) |
| `OPENAI_REASONING_MODEL` | gpt-5.4 | Text reasoning model (`gpt-5.4` or `gpt-5.3-instant`) |
| `ELEVENLABS_API_KEY` | Optional | ElevenLabs API key for TTS/STT |
| `ELEVENLABS_MODEL` | eleven_flash_v2_5 | ElevenLabs model (`eleven_flash_v2_5` or `eleven_multilingual_v2`) |
| `TTS_PROVIDER` | openai | TTS provider (`openai` or `elevenlabs`) |
| `STT_PROVIDER` | openai | STT provider (`openai` or `elevenlabs`) |
| `WEB_PORT` | 8000 | Web server port |
| `MAX_FILE_SIZE` | 50MB | Maximum upload file size |
| `MAX_CONTEXT_TOKENS` | 256000 | Context window token limit |
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
- **Silero VAD**: ML-based voice activity detection (replaces amplitude thresholds)
- **OpenAI Realtime API**: gpt-realtime (GA) for voice processing, gpt-realtime-mini for passive mode
- **Provider Layer**: Pluggable TTS/STT with OpenAI and ElevenLabs implementations
- **GPT-5.4 Reasoning**: Text reasoning with 1M token context window
- **Observer Agent**: Background conversation analysis with insight generation
- **Web Interface**: FastAPI-based dashboard with provider/model selectors
- **Document Processor**: Extracts and chunks uploaded documents
- **Vector Store**: ChromaDB for semantic document search
- **Context Manager**: Progressive summarization, topic extraction, document RAG, key-point notes

### Audio Pipeline

```
Discord Voice → Silero VAD → Audio Processing → OpenAI Realtime API → AI Response → Discord Voice
                                                      ↕
                                              (gpt-realtime or gpt-realtime-mini)
```

### Context Flow

```
Conversation → Summarizer (gpt-5.3-instant) → Topic Extraction → Document RAG → Context Window
     ↓
Observer Agent → Talking Points / Fact-Checks / Insights → Dashboard
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
- `GET /api/providers` - Get current TTS/STT providers and models
- `POST /api/providers/tts` - Switch TTS provider
- `POST /api/providers/stt` - Switch STT provider
- `POST /api/providers/reasoning-model` - Switch reasoning model
- `GET /api/voices` - List available voices for current TTS provider
- `GET /api/observer/insights` - Get AI-generated conversation insights
- `POST /api/observer/configure` - Configure observer analysis frequency

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

### API Costs (Approximate)

| Component | Provider | Cost |
|-----------|----------|------|
| Passive STT (per min) | gpt-realtime-mini | ~$0.02 |
| Active voice (per min) | gpt-realtime | ~$0.30 |
| TTS output (per min) | ElevenLabs Flash v2.5 | ~$0.06 |
| TTS output (per min) | OpenAI TTS-1 | ~$0.015 |
| Text reasoning (per 1K tokens) | gpt-5.4 | ~$0.005 |
| Text reasoning (per 1K tokens) | gpt-5.3-instant | ~$0.002 |
| Summarization (per 1K tokens) | gpt-5.3-instant | ~$0.002 |

**Estimated cost for 60-minute podcast**: ~$2-4 (with split-stack optimization)

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
   - Verify API key has Realtime API access
   - Check API usage limits and billing
   - Monitor rate limits

5. **ElevenLabs not working**
   - Verify `ELEVENLABS_API_KEY` is set in `.env`
   - Check your ElevenLabs plan has sufficient credits
   - Ensure `TTS_PROVIDER=elevenlabs` or `STT_PROVIDER=elevenlabs` is set

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
- [ ] Custom voice training / voice cloning (ElevenLabs)
- [ ] Twitch/YouTube chat integration
- [ ] Advanced analytics dashboard
- [ ] Plugin system for extensions
- [ ] Mobile app for remote control
- [ ] Multi-agent handoffs (inspired by LiveKit patterns)
- [ ] SIP/phone call integration
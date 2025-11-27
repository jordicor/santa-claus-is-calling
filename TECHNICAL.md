# Technical Documentation - Santa Claus is Calling

## Table of Contents
1. [System Overview](#system-overview)
2. [Architecture](#architecture)
3. [Core Components](#core-components)
4. [Technology Stack](#technology-stack)
5. [Features](#features)
6. [Security Measures](#security-measures)
7. [Database Schema](#database-schema)
8. [API Integrations](#api-integrations)
9. [Call Flow](#call-flow)
10. [Deployment](#deployment)

## System Overview

**Santa Claus is Calling** is a real-time voice interaction system that enables personalized phone calls from an AI-powered Santa Claus to children. The system orchestrates multiple cutting-edge technologies to create a magical experience through actual phone calls (not an app or web-based call).

### Key Innovation Points
- **Real Phone Calls**: Uses Twilio to make actual phone calls to any phone number
- **Real-time AI Conversation**: Integrates speech recognition, AI processing, and text-to-speech in real-time
- **Prompt Injection Protection**: Advanced prompt engineering techniques to maintain character integrity
- **Multi-language Support**: Available in 21+ languages
- **Scheduled Calls**: Parents can schedule calls for specific dates and times

## Architecture

The system follows a modular architecture with three main components:

```
┌─────────────────────────────────────────────────────────┐
│                     Web Application                      │
│                    (Flask - app.py)                      │
│  - User registration & authentication                    │
│  - Payment processing                                    │
│  - Call scheduling                                       │
│  - User dashboard                                        │
│  - Port 6789                                            │
└────────────────────┬────────────────────────────────────┘
                     │ HTTP (localhost:7778)
┌────────────────────┴────────────────────────────────────┐
│                  Call Processing System                  │
│            (FastAPI - austin-to-santa.py)               │
│  - WebSocket server for real-time audio                 │
│  - Speech-to-Text (Deepgram/Whisper)                   │
│  - AI Processing (OpenAI GPT-4/Claude)                  │
│  - Text-to-Speech (ElevenLabs)                         │
│  - Call state management                                │
│  - Port 7777 (HTTPS) + Port 7778 (HTTP)                │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────┴────────────────────────────────────┐
│                   External Services                      │
│  - Twilio (Voice calls & SMS)                          │
│  - OpenAI/Anthropic (AI conversation)                   │
│  - Deepgram (Speech recognition)                        │
│  - ElevenLabs (Voice synthesis)                         │
│  - PayPal (Payment processing)                          │
│  - Postmark (Email notifications)                       │
└─────────────────────────────────────────────────────────┘
```

## Core Components

### 1. Web Application (app.py)
- **Framework**: Flask with session management
- **Features**:
  - User registration with email verification
  - Secure authentication system with bcrypt
  - Payment integration with PayPal
  - Call scheduling interface
  - User dashboard for managing calls
  - Multi-language support (21 languages)
  - Discount code system

### 2. Call Processing System (austin-to-santa.py)
- **Framework**: FastAPI with WebSocket support
- **Real-time Processing Pipeline**:
  1. Twilio forwards call audio stream via WebSocket
  2. Audio chunks are processed and transcribed (Deepgram/Whisper)
  3. Transcriptions sent to AI model with context
  4. AI response generated maintaining Santa character
  5. Response converted to speech (ElevenLabs)
  6. Audio streamed back to caller

### 3. Call Initiator (caller.py)
- Simple Python script to trigger scheduled calls
- Retrieves user data from database
- Initiates Twilio call with proper webhook URL

## Technology Stack

### Backend
- **Python 3.x**: Core programming language
- **Flask**: Web application framework
- **FastAPI**: Async API framework for real-time processing
- **SQLite**: Database for user and call data
- **APScheduler**: Background job scheduling

### AI/ML Services
- **OpenAI GPT-4**: Primary conversation AI
- **Anthropic Claude**: Alternative AI model
- **Deepgram**: Real-time speech-to-text
- **OpenAI Whisper**: Backup speech recognition
- **ElevenLabs**: High-quality text-to-speech with Santa voice

### Communication
- **Twilio**: Voice calls and SMS verification
- **WebSockets**: Real-time bidirectional audio streaming
- **Postmark**: Transactional email service

### Frontend
- **HTML/CSS/JavaScript**: Responsive web interface
- **Bootstrap-inspired styling**: Custom Christmas theme
- **AJAX**: Dynamic content loading

### Security & Authentication
- **bcrypt**: Password hashing
- **JWT-like tokens**: Session management
- **SSL/TLS**: Encrypted communications
- **Rate limiting**: API protection

## Features

### User Features
1. **Registration & Authentication**
   - Email-based registration
   - Phone number verification via Twilio
   - Secure password reset functionality

2. **Call Management**
   - Schedule calls for specific date/time
   - Time zone support
   - Call duration selection (1-10 minutes)
   - Cancel scheduled calls

3. **Personalization**
   - Child's name and parents' names
   - Gift wishlist
   - Additional context for conversation
   - Language preference

4. **Payment System**
   - PayPal integration
   - Discount codes
   - Variable pricing based on call duration

### Admin Features
1. **Discount Code Management**
   - Create custom discount codes
   - Set validity periods
   - Usage limits

2. **User Management**
   - View registered users
   - Monitor call statistics

### AI Santa Features
1. **Character Consistency**
   - Maintains Santa persona throughout
   - Christmas-themed responses
   - Child-appropriate language

2. **Conversation Management**
   - Verifies child's identity at call start
   - Personalized gift discussions
   - Time management (warning before call ends)
   - Graceful call termination

3. **Safety Features**
   - No personal information collection from children
   - Positive value promotion
   - Inappropriate topic avoidance

## Security Measures

### Prompt Injection Protection
The system implements multiple layers of protection against prompt injection:

1. **Secret Keywords**: Uses unpredictable keywords for instruction modification
2. **Character Lock**: Santa cannot break character or reveal system prompts
3. **Instruction Hierarchy**: User inputs cannot override core instructions
4. **Content Moderation**: OpenAI moderation API filters inappropriate content
5. **Response Reversal**: Malicious requests trigger reversed responses

### Data Security
1. **Password Security**:
   - bcrypt hashing with salt
   - Additional pepper for extra security
   - Secure password reset tokens

2. **Session Security**:
   - HTTPOnly cookies
   - Secure cookie flag for HTTPS
   - Session timeout

3. **Database Security**:
   - Parameterized queries (SQL injection prevention)
   - Input validation and sanitization

4. **API Security**:
   - Environment variables for credentials
   - CloudFlare origin verification option
   - Rate limiting on sensitive endpoints

## Database Schema

### Tables

#### users
- `id`: Primary key
- `email`: Unique user email
- `password`: Hashed password
- `lang`: User's preferred language
- `role_id`: Foreign key to role table

#### user_details
- `id`: Primary key
- `user_id`: Foreign key to users
- `child_name`: Name of the child
- `father_name`: Father's name (optional)
- `mother_name`: Mother's name (optional)
- `phone_number`: Contact number
- `gifts`: Gift wishlist
- `context`: Additional context

#### calls
- `id`: Primary key
- `user_id`: Foreign key to users
- `call_date`: Scheduled date
- `call_time`: Scheduled time
- `time_zone`: User's timezone
- `verification_code`: Phone verification code
- `call_job_id`: APScheduler job ID
- `timer`: Call duration in minutes

#### discounts
- `code`: Primary key (discount code)
- `discount_value`: Percentage or fixed discount
- `active`: Boolean status
- `validity_date`: Expiration date
- `usage_count`: Number of uses
- `unlimited_usage`: Boolean flag
- `unlimited_validity`: Boolean flag

## API Integrations

### Twilio Integration
- **Voice Calls**: Outbound call initiation
- **WebSocket Streaming**: Real-time audio transfer
- **SMS**: Phone verification codes
- **TwiML**: Call flow control

### OpenAI Integration
- **GPT-4**: Main conversation model
- **Whisper**: Speech-to-text backup
- **Moderation API**: Content filtering

### ElevenLabs Integration
- **Voice Cloning**: Custom Santa voice
- **Real-time TTS**: Low-latency speech generation
- **Voice Settings**: Stability and similarity tuning

### PayPal Integration
- **Sandbox Support**: Testing environment
- **Order Creation**: Dynamic pricing
- **Payment Capture**: Secure transaction processing

## Call Flow

```
1. Parent schedules call via web interface
   ↓
2. System stores call details and schedules job
   ↓
3. At scheduled time, caller.py initiates call
   ↓
4. Twilio connects to austin-to-santa.py webhook
   ↓
5. WebSocket connection established for audio stream
   ↓
6. Audio Loop:
   a. Receive audio chunks from Twilio
   b. Transcribe speech (Deepgram/Whisper)
   c. Process with AI (GPT-4/Claude)
   d. Generate speech (ElevenLabs)
   e. Stream audio back to caller
   ↓
7. Call termination (time limit or user hangup)
   ↓
8. Cleanup and logging
```

## Deployment

### Requirements
- Python 3.8+
- SSL certificate for HTTPS
- Domain name for webhooks
- API keys for all services

### Environment Setup
1. Copy `.env.example` to `.env`
2. Fill in all API credentials
3. Configure database path
4. Set security keys and salts

### Installation
```bash
# Install dependencies
pip install -r requirements.txt

# Initialize database
python init_db.py

# Run web application
python app.py

# Run call processing server
uvicorn austin-to-santa:app --reload
```

### Production Considerations
1. **Scaling**: Use gunicorn/uvicorn workers
2. **Database**: Consider PostgreSQL for production
3. **Caching**: Implement Redis for session storage
4. **Monitoring**: Add logging and error tracking
5. **Backup**: Regular database backups
6. **SSL**: Ensure all endpoints use HTTPS

## Performance Optimizations

### Audio Processing
- Chunked streaming for low latency
- Audio format optimization (mulaw for telephony)
- Buffer management for smooth playback

### AI Response
- Token limits for faster responses
- Conversation context management
- Response caching for common queries

### Database
- Indexed queries for user lookups
- Connection pooling for concurrent access
- Regular maintenance and optimization

## Limitations and Known Issues

1. **File-based Storage**: Currently uses text files for some data (could be migrated to database)
2. **Single Server**: No built-in horizontal scaling
3. **Language Models**: Response quality depends on AI model capabilities
4. **Network Dependency**: Requires stable internet for all external services
5. **Cost**: Each call incurs costs from multiple services (Twilio, AI, TTS)

## Contributing

This project was developed as a learning experience and proof of concept. While it may not follow all professional best practices, it demonstrates the integration of multiple modern technologies to create a unique user experience.

### Areas for Contribution
- Code refactoring and optimization
- Security enhancements
- Documentation improvements
- Bug fixes
- Feature additions
- Internationalization

## License

See LICENSE file for details.

## Acknowledgments

This project was created as a personal learning experience after years away from programming, leveraging AI assistance to get back up to speed with modern web development. It represents hundreds of hours of testing, prompt engineering, and integration work to create a magical experience for children during the holiday season.

Special thanks to the open-source community and the developers of all the integrated services that made this project possible.
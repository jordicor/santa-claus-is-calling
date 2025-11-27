# 🎅 Quick Start - Get Santa Calling in 15 Minutes

Just want to test it quickly? Follow these steps:

## 1️⃣ Get Essential API Keys (5 min)

You need 4 services minimum:
- **Twilio**: https://www.twilio.com/try-twilio → Get Account SID, Auth Token, buy a phone number ($1)
- **OpenAI**: https://platform.openai.com/api-keys → Create an API key
- **Deepgram**: https://console.deepgram.com → Get your API key (free credits included)
- **ElevenLabs**: https://elevenlabs.io → Get API key from your profile

## 2️⃣ Setup (5 min)

```bash
# Clone and enter directory
git clone https://github.com/yourusername/santa-claus-is-calling.git
cd santa-claus-is-calling

# Install packages
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your API keys (use any text editor)

# Initialize database
python init_db.py

# (Optional) If using Cloudflare Tunnel or similar, the app already runs
# an HTTP server on port 7778 that you can use instead of the HTTPS one (7777)
```

## 3️⃣ Expose to Internet (2 min)

Download [ngrok](https://ngrok.com/download) then:

```bash
# Terminal 1 - Web app
ngrok http 6789

# Terminal 2 - Call processor (use 7778 for HTTP or 7777 for HTTPS)
ngrok http 7778
```

Save both URLs you get (like `https://abc123.ngrok.io`)

## 4️⃣ Configure Twilio (2 min)

1. Go to Twilio Console → Phone Numbers → Your Number
2. Set webhook URL to: `https://[your-ngrok-url]/answer/{user_id}/{call_job_id}`

## 5️⃣ Run It! (1 min)

```bash
# Terminal 3
python app.py

# Terminal 4
python austin-to-santa.py
```

## 6️⃣ Test

1. Go to `http://localhost:6789`
2. Register (confirmation link appears on screen)
3. Schedule a call
4. Use discount code **TEST100** for free testing
5. Wait for Santa to call!

---

**Need more details?** Check the full [Deployment Guide](DEPLOYMENT.md)

**Having issues?** Common problems:
- Both Python scripts must be running
- ngrok URLs must be active
- Twilio webhook must point to your ngrok URL for the call processor
- Use port 7778 (HTTP) with ngrok/Cloudflare Tunnel, or 7777 (HTTPS) with certificates

🎄 **Happy Testing!**
# 🚀 Deployment Guide - Santa Claus is Calling

This guide will help you get Santa calling in about 30 minutes. Don't worry if you're not super technical - we'll walk through everything step by step.

## 📋 Before You Start

You'll need accounts with several services to make the magic happen. Most offer free tiers or trial periods perfect for testing.

### What This Will Cost You

**For Testing**: Almost nothing! Use the TEST100 discount code and sandbox environments.

**For Real Calls**:
- Twilio: ~$0.015/minute + $1/month for a phone number
- AI Services: ~$0.10-0.30 per call depending on length
- Text-to-Speech: ~$0.30 per call

---

## 🔑 Step 1: Get Your API Keys

Let's start by signing up for the services we need. Open each link in a new tab and sign up - it'll take about 10 minutes total.

### Core Services (Required)

#### Twilio - Makes the Phone Calls
1. Sign up at https://www.twilio.com/try-twilio
2. Verify your email and phone number
3. From your [Console Dashboard](https://console.twilio.com):
   - Copy your **Account SID** (starts with AC...)
   - Copy your **Auth Token** (click to reveal it)
   - Buy a phone number ($1/month) - click "Phone Numbers" → "Buy a Number"
   - Save the phone number for later

#### OpenAI or Anthropic - Santa's Brain
Pick ONE of these:

**Option A: OpenAI (GPT-4)**
1. Sign up at https://platform.openai.com/signup
2. Go to [API Keys](https://platform.openai.com/api-keys)
3. Click "Create new secret key"
4. Copy and save it immediately (you can't see it again!)

**Option B: Anthropic (Claude)**
1. Sign up at https://console.anthropic.com
2. Go to API Keys section
3. Create and copy your key

#### Deepgram - Understands What Kids Say
1. Sign up at https://console.deepgram.com/signup
2. Create a new API key from your dashboard
3. The free tier gives you $200 in credits - plenty for testing!

#### ElevenLabs - Santa's Voice
1. Sign up at https://elevenlabs.io/sign-up
2. Go to your [Profile](https://elevenlabs.io/profile)
3. Copy your API key
4. Note: We'll use voice ID `Gqe8GJJLg3haJkTwYj2L` for Santa

### Optional Services

#### PayPal - Handle Payments (Skip for Testing)
1. Go to https://developer.paypal.com
2. Log in with your PayPal account
3. Go to [Sandbox Dashboard](https://developer.paypal.com/dashboard/applications/sandbox)
4. Create a new app
5. Copy the Client ID and Secret

**Remember**: Sandbox = fake money for testing. Perfect!

#### Postmark - Send Emails (Currently Disabled)
The email features are turned off by default, but if you want them:
1. Sign up at https://postmarkapp.com
2. Get your Server Token from the Servers page

---

## 🔧 Step 2: Set Up the Application

### Install the Code

1. **Clone or download the project**:
```bash
git clone https://github.com/yourusername/santa-claus-is-calling.git
cd santa-claus-is-calling
```

2. **Install Python packages**:
```bash
pip install -r requirements.txt
```

3. **Set up your configuration**:
```bash
# Copy the example file
cp .env.example .env

# Now edit .env with your favorite text editor
# On Windows: notepad .env
# On Mac/Linux: nano .env
```

4. **Fill in your API keys** in the `.env` file:
```env
# The keys you just collected
OPENAI_KEY=sk-proj-xxxxx...
TWILIO_SID=ACxxxxx...
TWILIO_AUTH=xxxxx...
TWILIO_NUMBER=+1234567890
DEEPGRAM_KEY=xxxxx...
ELEVEN_KEY=xxxxx...

# Set your AI preference (GPT or Claude)
LLM_AI=GPT
```

5. **Initialize the database**:
```bash
python init_db.py
```

### Choose Your SSL Setup

The call processing server (austin-to-santa.py) now runs **two servers**:
- **Port 7777 (HTTPS)**: For direct access with SSL certificates
- **Port 7778 (HTTP)**: For use with Cloudflare Tunnel, ngrok, or internal communication

#### Option 1: Use HTTP Server (Easiest - Recommended for Testing)

Simply use port **7778** instead of 7777. This is perfect for:
- Cloudflare Tunnel (which provides SSL for you)
- ngrok (which provides SSL for you)
- Local testing

No configuration changes needed - just point your tunnel/ngrok to port 7778.

#### Option 2: Self-Signed Certificates (Local Testing)

Quick and easy for local development:
```bash
# Create the certificates directory
mkdir -p static/sec

# Generate self-signed certificates (just press Enter for all prompts)
openssl req -x509 -newkey rsa:4096 -keyout static/sec/privkey.pem -out static/sec/cert.pem -days 365 -nodes
```

Your browser will warn about these certificates - that's normal for self-signed certs.

#### Option 3: Real SSL Certificates (Production)

For a production deployment with a real domain:
1. Visit https://certbot.eff.org/
2. Follow the instructions for your operating system
3. Copy the generated certificates to `static/sec/`

---

## 🌐 Step 3: Make It Accessible to the Internet

Twilio needs to reach your application, so we need to expose it to the internet. Here are three ways, from easiest to most professional:

### Option A: ngrok (Fastest - 2 minutes)

Perfect for quick testing. Download from https://ngrok.com/download, then:

```bash
# Terminal 1 - Expose the web app
ngrok http 6789

# Terminal 2 - Expose the call processor (HTTP server)
ngrok http 7778
```

You'll get URLs like `https://abc123.ngrok.io` - save these for the next step!

### Option B: Cloudflare Tunnel (Best for Production)

More reliable and you can use your own domain. Uses the HTTP server (port 7778) since Cloudflare provides SSL:

1. **Install cloudflared**:
   - Windows: `winget install Cloudflare.cloudflared`
   - Mac: `brew install cloudflared`
   - Linux: See [official guide](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/)

2. **Login to Cloudflare**:
```bash
cloudflared tunnel login
```

3. **Create tunnels**:
```bash
# Terminal 1 - Web interface
cloudflared tunnel --url http://localhost:6789 --hostname santa.yourdomain.com

# Terminal 2 - Call processor (use HTTP port since Cloudflare provides SSL)
cloudflared tunnel --url http://localhost:7778 --hostname api-santa.yourdomain.com
```

### Option C: LocalTunnel (Free Alternative)

Another free option if ngrok limits are an issue:

```bash
# Install it first
npm install -g localtunnel

# Terminal 1 - Web app
lt --port 6789 --subdomain my-santa-app

# Terminal 2 - Call processor (HTTP server)
lt --port 7778 --subdomain my-santa-api
```

---

## 📞 Step 4: Configure Twilio

Now we need to tell Twilio where to send the calls:

1. **Go to your Twilio Console**
2. **Find your phone number** under Phone Numbers → Manage → Active Numbers
3. **Click on your number** to configure it
4. **In the Voice Configuration section**, set:
   - "A call comes in" → Webhook
   - URL: `https://your-api-url/answer/{user_id}/{call_job_id}`
   - Method: POST

   Replace `your-api-url` with your ngrok/tunnel URL from Step 3 (the URL includes the port already).

### Set Up the Introduction Audio

You have two options for Santa's introduction message:

#### Option A: Local Files (Easier)
Create these files:
- `static/audio/intro-Spanish.mp3`
- `static/audio/intro-English.mp3`

Record something like: "Ho ho ho! This is Santa Claus calling! May I speak with [child's name]?"

#### Option B: Twilio Assets (More Reliable)
1. Go to Twilio Console → Develop → Assets & Functions → Assets
2. Upload your intro MP3 file
3. Copy the URL
4. Add to your `.env`: `INTRO_AUDIO_URL=https://your-asset-url.twil.io/intro.mp3`

---

## 🎮 Step 5: Run the Application

Time to bring Santa to life! You'll need two terminal windows:

**Terminal 1 - Web Application**:
```bash
python app.py
```
You should see: `Running on http://0.0.0.0:6789`

**Terminal 2 - Call Processor**:
```bash
python austin-to-santa.py
```
You should see:
- `HTTP server started on port 7778`
- `HTTPS server starting on port 7777`

---

## 🧪 Step 6: Test Everything

### Quick Test Checklist

1. **Open the web app**: Go to `http://localhost:6789` (or your tunnel URL)

2. **Register a test account**:
   - Use any email (emails aren't being sent by default)
   - The confirmation link will appear on screen - click it

3. **Schedule a test call**:
   - Enter child and parent names
   - Add a wishlist
   - Use the discount code **TEST100** for free testing
   - Schedule for a few minutes from now

4. **Wait for the magic**: Santa will call at the scheduled time!

### Test Without Payment

The system includes several ways to test for free:

- **PayPal Sandbox**: All transactions are fake
- **Discount Code TEST100**: Gives 100% discount (completely free)
- **Create Custom Codes**: Visit `/create-discount` as an admin

### Troubleshooting Common Issues

**Santa doesn't call:**
- Check your Twilio webhook URL is correct
- Make sure both Python scripts are running
- Check the terminal windows for error messages

**Can't hear Santa or Santa can't hear the caller:**
- Check your Deepgram API key
- Verify ElevenLabs API key
- Look for errors in the austin-to-santa.py terminal

**SSL Certificate errors:**
- Use port 7778 (HTTP) if using Cloudflare Tunnel or ngrok - they provide SSL for you
- For direct HTTPS access (port 7777), you need certificates in `static/sec/`

---

## 📧 Note About Emails

The email system is currently **disabled** to make testing easier. When you register or reset a password, the links appear directly on the webpage instead of being emailed.

To enable emails:
1. Get a Postmark API key
2. Add it to your `.env` file
3. Edit `app.py` and uncomment the lines with `send_confirmation_email()`
4. Configure your "from" email address in Postmark

---

## 💡 Pro Tips

### Keep Costs Low
- Use the free tiers while testing
- Set call timers to 1-2 minutes initially
- Monitor your usage in each service's dashboard

### Security Notes
- Never commit your `.env` file to git
- Regenerate API keys if you accidentally expose them
- Use strong passwords for admin accounts

### Testing with Kids
- Do a test call yourself first
- Keep initial calls short (1-2 minutes)
- Have the wishlist ready beforehand
- Make sure the phone volume is up!

---

## 🎄 Ready to Spread Joy!

Congratulations! You now have Santa Claus ready to make magical phone calls. Remember:

- Start with test calls to yourself
- Use discount codes for free testing
- Monitor the console for any errors
- Have fun and make magic happen!

If you run into issues, check the [Technical Documentation](TECHNICAL.md) or open an issue on GitHub.

**Ho Ho Ho! Let the Christmas magic begin!** 🎅📞
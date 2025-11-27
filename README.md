# 🎅 Santa Claus is Calling - Real AI Phone Calls from Santa

<div align="center">
  <img src="static/img/santa_claus____.jpg" alt="Santa Claus is Calling" width="600">
</div>

<div align="center">
  <img src="https://img.shields.io/badge/Status-Working-green" alt="Status">
  <img src="https://img.shields.io/badge/Python-3.8+-blue" alt="Python">
  <img src="https://img.shields.io/badge/License-MIT-yellow" alt="License">
  <img src="https://img.shields.io/badge/AI-GPT--4%20%7C%20Claude-purple" alt="AI">
</div>

<div align="center">
  <h3>🎄 A magical Christmas experience where Santa Claus actually calls children on the phone 🎄</h3>
  <p><strong>Real phone calls</strong> • <strong>Real-time AI conversation</strong> • <strong>21+ languages</strong> • <strong>Personalized experience</strong></p>
</div>

## 📖 The Story Behind This Project

Two years ago, after many years away from programming and focusing on audiovisual content creation, SEO, marketing, and finance, the emergence of AI tools like ChatGPT reignited my passion for coding. This project became my way back into development - an ambitious undertaking that combines cutting-edge AI technology with the magic of Christmas.

**Santa Claus is Calling** is a system that makes **actual phone calls** to children, where they can have real conversations with an AI-powered Santa Claus. The children hear their phone ring, see an unknown number, answer it, and hear Santa's voice asking for them by name. It's pure magic.

### Why This Project Exists

The initial vision was to create a business model where:
- Parents could register their children for personalized Santa calls
- Children could tell Santa their wish lists
- Santa would call back after Christmas to ask about their gifts
- Parents would receive insights about their children's conversations (detecting issues like bullying)
- Affiliate links would help parents purchase the exact toys their children wanted

However, as a solo developer juggling multiple projects, and with companies like ElevenLabs launching similar (though web-based) solutions, I decided to open-source this project. While it may not be "production-perfect" (it uses text files for some data storage, among other pragmatic choices), it **works** and has been thoroughly tested.

### What Makes This Special

This was built when:
- Real-time voice AI APIs didn't exist yet - I had to orchestrate everything manually
- AI models were much easier to "jailbreak" - I developed unique prompt protection techniques
- There were no frameworks for this - everything is built from scratch

The result? A system resistant to prompt injection (using hypnosis-like session techniques and secret keywords), capable of maintaining character for entire conversations, and able to handle real-time phone interactions in 21+ languages.

## ✨ Features

### For Children & Families
- 📞 **Real Phone Calls**: Not a web app - Santa actually calls your phone
- 🎅 **Authentic Santa Experience**: Carefully crafted AI personality that never breaks character
- 🎁 **Personalized Conversations**: Santa knows the child's name, parents' names, and wish list
- 🌍 **21+ Languages**: Santa speaks your language fluently
- ⏰ **Scheduled Calls**: Set the exact date and time for Santa to call
- 🎭 **Character Consistency**: Advanced prompt engineering prevents breaking character

### For Developers
- 🔧 **Complete System**: From user registration to call execution
- 🛡️ **Security First**: Bcrypt + pepper, SQL injection prevention, prompt injection protection
- 📊 **Full Admin Panel**: User management, discount codes, call monitoring
- 💳 **Payment Integration**: PayPal ready (sandbox included)
- 📧 **Email Notifications**: Postmark integration for transactional emails
- 🔄 **Real-time Processing**: WebSocket-based audio streaming

### Technical Highlights
- **No Frameworks**: Built from scratch for maximum learning and control
- **Multi-Service Orchestration**: Seamlessly connects Twilio, OpenAI/Claude, Deepgram, and ElevenLabs
- **Prompt Injection Resistant**: Unique protection mechanisms developed before they were common
- **Scalable Architecture**: Separation between web app and call processing system

## 📸 Screenshots

<div align="center">
  <table>
    <tr>
      <td align="center">
        <img src="static/img/Screenshot-01.jpg" alt="Login & Landing Page" width="400"><br>
        <sub><b>Login & Landing Page</b></sub>
      </td>
      <td align="center">
        <img src="static/img/Screenshot-03.jpg" alt="Child Profile Configuration" width="400"><br>
        <sub><b>Child Profile Configuration</b></sub>
      </td>
    </tr>
  </table>
</div>

## 🚀 Quick Start

**Want to test it in 15 minutes?** Check our **[Quick Start Guide](QUICKSTART.md)**!

### Prerequisites
- Python 3.8+
- Accounts and API keys for:
  - Twilio (phone calls)
  - OpenAI or Anthropic (AI conversation)
  - Deepgram (speech recognition)
  - ElevenLabs (voice synthesis)
  - PayPal (payments - optional)
  - Postmark (emails - optional)

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/yourusername/santa-claus-is-calling.git
cd santa-claus-is-calling
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Configure environment**
```bash
cp .env.example .env
# Edit .env with your API keys and configuration
```

4. **Initialize database**
```bash
python init_db.py
```

5. **Run the web application**
```bash
python app.py
# Runs on port 6789
```

6. **Run the call processing server** (in another terminal)
```bash
python austin-to-santa.py
# Runs on port 7777 with SSL
```

7. **Access the application**
```
http://localhost:6789
```

📌 **Note**: For detailed setup instructions including how to expose your application to the internet (required for Twilio webhooks), SSL configuration options, and testing with discount codes, see the [Deployment Guide](DEPLOYMENT.md).

## 📚 Documentation

- **[Quick Start Guide](QUICKSTART.md)**: Get Santa calling in 15 minutes
- **[Deployment Guide](DEPLOYMENT.md)**: Complete setup and deployment instructions
- **[Technical Documentation](TECHNICAL.md)**: Detailed architecture, components, and implementation details
- **[Contributing Guide](CONTRIBUTING.md)**: How to contribute to the project

## 🎯 Use Cases

### Current Implementation
- **Christmas Magic**: Children receive personalized calls from Santa
- **Gift Planning**: Parents know exactly what their children want
- **Language Practice**: Children can practice languages with Santa
- **Special Occasions**: Adaptable for birthdays or other celebrations

### Potential Expansions
- **Other Characters**: Easter Bunny, Tooth Fairy, Birthday Fairy
- **Educational Calls**: Historical figures, scientists, book characters
- **Elderly Companionship**: Regular check-in calls for seniors
- **Language Learning**: Practice conversations with native speakers
- **Customer Service Training**: Simulate difficult customer scenarios

## 💡 The Technical Journey

### Challenges Overcome
1. **Real-time Audio Processing**: Orchestrating multiple services with minimal latency
2. **Character Consistency**: Developing prompt engineering techniques before they were common
3. **Security**: Protecting against both technical and social engineering attacks
4. **Multi-language Support**: Handling cultural differences in how Santa is perceived
5. **Child Safety**: Ensuring appropriate content while maintaining engaging conversations

### Lessons Learned
- **Simplicity Works**: Text files and SQLite can go surprisingly far
- **User Experience First**: Real phone calls create magic that apps can't match
- **Prompt Engineering is an Art**: The difference between good and great is in the details
- **Testing with Real Users**: Children are the ultimate QA testers
- **Open Source Value**: What didn't become a business can still help others

## 🤝 Contributing

This project is now open source and welcomes contributions! Whether you're interested in:
- 🎨 Improving the UI/UX
- 🔧 Refactoring code
- 📝 Improving documentation
- 🌍 Adding translations
- 🐛 Fixing bugs
- ✨ Adding features

All contributions are welcome! This project was a learning journey, and it can be yours too.

## ⚠️ Important Notes

### Current Limitations
- **File Storage**: Some data uses text files (works but not ideal for scale)
- **Single Server**: Not designed for horizontal scaling (yet)
- **Cost**: Each call incurs real costs (Twilio + AI + TTS) - but use code **TEST100** for free testing!
- **Manual Setup**: Requires technical knowledge to deploy
- **Email System**: Currently disabled by default (links appear on screen instead)

### Ethical Considerations
- **Child Safety**: Never collect personal information from children
- **Transparency**: Parents should know it's AI-powered
- **Data Privacy**: Consider GDPR/COPPA compliance for production use
- **Content Moderation**: Monitor conversations for safety

## 📊 Project Status

This project is **functional and tested** but was ultimately not launched as a business. It represents hundreds of hours of development, testing, and refinement. While companies with more resources have since launched similar services, this remains unique as:
- A fully open-source solution
- Using real phone calls (not web-based)
- With advanced prompt protection techniques
- Built from scratch without frameworks

## 🙏 Acknowledgments

### Special Thanks To
- **The AI Community**: For making powerful tools accessible
- **Open Source Contributors**: Whose libraries made this possible
- **Early Testers**: The children who helped perfect Santa's personality
- **You**: For reading this and potentially continuing the journey

### Technologies Used
- **Twilio**: For making phone calls possible
- **OpenAI & Anthropic**: For the AI that brings Santa to life
- **Deepgram**: For understanding children's excited voices
- **ElevenLabs**: For Santa's magical voice
- **Python Community**: For the amazing ecosystem

## 📜 License

This project is released under the MIT License. Use it, learn from it, build upon it - and if you create something magical, please share it with the world.

## 🎁 Final Thoughts

This project started as a "what if" - what if Santa could really call children? What if AI could create genuine magical moments? What if technology could make Christmas more special?

While it didn't become the business I envisioned, it taught me invaluable lessons about modern development, AI integration, and the joy of creating something meaningful. If even one child smiles because of this code, or one developer learns something new from it, then sharing it was worth it.

The code may not be perfect (you'll find some Spanish comments I might have missed, some text files doing database work, and other "pragmatic" choices), but it works, it's tested, and most importantly - it creates magic.

**Welcome to Santa Claus is Calling. May your holidays be filled with wonder, and your code with joy.**

---

<div align="center">
  <img src="static/img/santa_chibi.png" alt="Santa" width="80">
  <img src="static/img/Reno_chibi.png" alt="Rudolph" width="80">
  <img src="static/img/regalo_chibi.png" alt="Gift" width="80">
  <p>🎅 Ho Ho Ho! Happy Coding! 🎄</p>
  <p><sub>Created with ❤️ and lots of testing by someone who believes in Christmas magic and open source</sub></p>
</div>
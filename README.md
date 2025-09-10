# 🌐 Web LiveKit + BeyondPresence Avatar

[![Node.js](https://img.shields.io/badge/Node.js-18%2B-green)](https://nodejs.org/)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![LiveKit](https://img.shields.io/badge/LiveKit-Cloud-orange)](https://livekit.io/cloud)
[![License](https://img.shields.io/badge/license-MIT-lightgrey.svg)](LICENSE)

Run a **Next.js web viewer** that streams a **BeyondPresence avatar** published by a **Python LiveKit agent**.  
This project integrates **LiveKit Cloud**, **BeyondPresence**, and **OpenAI** to deliver real-time, interactive avatars.

---

## ✨ Features
- 🧑‍💻 Next.js frontend for avatar playback  
- 🐍 Python agent publishes media to LiveKit  
- 🔑 Server-side JWT token generation (no static client tokens)  
- 🤖 BeyondPresence + OpenAI integration  
- 🚀 Fast local dev with `pnpm` + optional `uv` for Python

---

## ⚡ Prerequisites
You’ll need:
- [Node.js](https://nodejs.org/) **v18+**
- [Python](https://www.python.org/) **3.10+**
- A [LiveKit Cloud](https://livekit.io/cloud) project (URL, API Key, API Secret)
- A **BeyondPresence API key**
- An **OpenAI API key**

---

## 📦 Step 1 — Install dependencies
From the project root:

```bash
pnpm install   # or: npm install
```

## 🔑 Step 2 — Configure environment variables (secure)

Create `.env.local` in project root for the Next.js app:

```bash
NEXT_PUBLIC_BEY_API_KEY=your_beyondpresence_api_key
NEXT_PUBLIC_DEMO_AVATAR_ID=your_avatar_id
NEXT_PUBLIC_DEMO_LIVEKIT_URL=wss://your-project.livekit.cloud

LIVEKIT_API_KEY=your_livekit_api_key
LIVEKIT_API_SECRET=your_livekit_api_secret
```

Create `python-agent/.env` for the Python agent:

```bash
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your_livekit_api_key
LIVEKIT_API_SECRET=your_livekit_api_secret

OPENAI_API_KEY=sk-your-openai-key

# Optional personalization
BEY_AVATAR_ID=your_avatar_id
PT_USER_NAME=YourName
PT_USER_CONTEXT=Short profile or interests
PT_INTEREST_AREAS=comma,separated,topics
PT_RECENCY_DAYS=30
PT_DISALLOWED_TOPICS=comma,separated,disallowed
PT_LLM_MODEL=gpt-4o-mini
PT_TTS_VOICE=alloy
```

Notes:
- The web app auto-generates viewer JWTs using `LIVEKIT_API_KEY` and `LIVEKIT_API_SECRET`. You do not need to provide a static `NEXT_PUBLIC_DEMO_LIVEKIT_TOKEN`.
- Use the same LiveKit URL/key/secret in both apps.

## ▶️ Step 3 — Start the Python agent

Terminal 1:

```bash
cd python-agent
./run-uv.sh       # fast path using uv
# or
./run.sh          # venv + pip path
```

When running in dev mode, the agent connects to LiveKit using the env values and joins rooms created by the web app.

## 🌐 Step 4 — Start the Next.js app

Terminal 2:

```bash
pnpm dev  # or: npm run dev
```

Open `http://localhost:3000` and you should see the avatar stream. The app will show a configuration warning page until required env vars are set.

## 🧭 How it works (flow)

Python Agent ➜ LiveKit Cloud ➜ Next.js Viewer
The Python agent connects to LiveKit and publishes audio/video for the chosen avatar.
The Next.js app requests a server-generated JWT and joins the LiveKit room.
The viewer plays the avatar stream in real time.

## 🛠 Troubleshooting

❌ No video/audio → Ensure the Python agent is running and connected to LiveKit.

🔑 Token errors → Check LIVEKIT_API_KEY/LIVEKIT_API_SECRET in both .env.local and python-agent/.env.

🚫 401/403 from LiveKit → Verify LIVEKIT_URL and that the project credentials match.

🤖 OpenAI errors → Confirm OPENAI_API_KEY is set in python-agent/.env.

🔇 Autoplay blocked → Click anywhere in the page to enable audio playback.

🧪 Windows/WSL path issues → Prefer running the repo under your Linux home (e.g., ~/project) instead of /mnt/c/....

## 🧳 Scripts
**Web**

  pnpm dev — run dev server
  
  pnpm build — build for production
  
  pnpm start — start production server
  
  pnpm test — run tests

**Python**

  python-agent/run-uv.sh — run agent with uv
  
  python-agent/run.sh — run agent with venv + pip


=======
## Structure of the codebase
.
├─ python-agent/
│  ├─ run-uv.sh
│  ├─ run.sh
│  └─ .env
├─ app/ or pages/           # Next.js routes
├─ src/                     # Web app source
├─ .env.local               # Web env (private+public)
├─ package.json
└─ README.md

## Note

Add env files to .gitignore:

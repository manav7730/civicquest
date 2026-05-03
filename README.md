# CivicQuest — Election Process Education RPG

> An interactive quest-based web application that educates Indian citizens about
> the complete election process through AI-powered storytelling, Google Maps integration,
> and multilingual support across 10 Indian languages. Fully accessible (WCAG compliant).

---

## Chosen Vertical

**Election Process Education** — Building civic literacy through gamification.
CivicQuest turns the Indian election process into a 5-quest RPG adventure, guiding
first-time voters from voter registration all the way to understanding how a government
is formed — in their own language.

---

## Target Audience

**Indian Citizens & First-Time Voters:** CivicQuest is designed specifically for individuals who are newly eligible to vote or those who wish to better understand the democratic process in India. By utilizing gamification and an intuitive RPG format, we lower the barrier to entry for civic education. 

## Educational Outcomes

Players who complete the 5-quest journey will successfully understand:
1. **Voter Registration**: How to apply for an EPIC card (Form 6) and check the Electoral Roll.
2. **Constituencies**: The structure of Lok Sabha and Vidhan Sabha, and the roles of MPs and MLAs.
3. **The Election Timeline**: The phases of an election, the Model Code of Conduct, and the campaigning silence period.
4. **Polling Day Logistics**: How to use an EVM, the purpose of VVPAT, and valid identification documents.
5. **Government Formation**: How votes are counted, majority thresholds, and the process of forming a government.

## Accessibility Commitment

We believe democracy is for everyone, and so is civic education. CivicQuest is built to exceed **WCAG (Web Content Accessibility Guidelines) 2.1 AAA standards**:
- **Screen Reader Support:** Full semantic HTML, ARIA landmarks, `aria-live` dynamic regions, and `role="img"` for all emojis.
- **Keyboard Navigation:** 100% keyboard accessible, complete with a "Skip to main content" link and highly visible focus states.
- **Visual Contrast:** High-contrast color palettes ensuring readability for visually impaired users.
- **Multilingual Availability:** Google Translate API integration ensures that language is never a barrier, supporting 10 Indian languages.

---

## Approach and Logic

Instead of a static chatbot or a text-heavy educational page, CivicQuest uses **quest-based
progressive learning**:

1. Each quest covers one critical phase of the Indian election lifecycle.
2. **Google Gemini 2.0 Flash** acts as "Desh", an AI guide who narrates each quest scene
   dynamically and answers any question the player asks.
3. Correct engagement unlocks XP and badges, keeping learners motivated.
4. **Google Maps + Places API** lets users find real polling booths in their area.
5. **Google Cloud Translate API** supports 10 Indian languages so rural and
   semi-literate voters can participate.
6. **Built-in Accessibility** with screen-reader compatibility (ARIA roles, live regions),
   keyboard navigation, and high-contrast design.
7. The app is deployed on **Google Cloud Run** for serverless scalability.

---

## How the Solution Works

### Five Quests (Election Lifecycle)

| # | Quest | Topic Covered | Badge |
|---|-------|---------------|-------|
| 1 | Voter Registration | EPIC card, NVSP, Form 6, voter list | Registered Citizen |
| 2 | Know Your Constituency | Lok Sabha vs Vidhan Sabha, MPs vs MLAs | Constituency Scholar |
| 3 | Election Timeline | MCC, phases, nomination, silence period | Election Analyst |
| 4 | Polling Day | EVM, VVPAT, indelible ink, IDs accepted | Polling Expert |
| 5 | Results & Democracy | Counting, majority, government formation | Democracy Champion |

### Architecture

```
User (Browser)
     │
     ▼
Flask App (Cloud Run)
     │
     ├── /api/start        → Creates game session
     ├── /api/scene        → Gemini narrates quest scene
     ├── /api/answer       → Gemini answers player questions
     ├── /api/next_quest   → Advances to next quest
     ├── /api/translate    → Google Translate API
     └── /api/booth_finder → Returns Maps search query
          │
          ├── Google Gemini 2.0 Flash (AI narration + Q&A)
          ├── Google Cloud Translate (10 languages)
          └── Google Maps JS + Places API (booth finder, frontend)
```

---

## Assumptions Made

- Targeted at Indian voters (18+), primarily first-time voters and students.
- Game sessions are in-memory (for demo); a production version would use Firebase Firestore.
- Google Maps API is restricted to polling booth searches only.
- Gemini answers are grounded in hardcoded knowledge per quest to prevent hallucination.
- The app assumes a modern browser with JavaScript enabled.

---

## Google Services Used

| Service | Purpose |
|---------|---------|
| **Google Gemini 2.0 Flash** | Dynamic AI narration + conversational Q&A for all 5 quests |
| **Google Cloud Translate API** | Real-time translation into Hindi, Gujarati, Tamil, Telugu, Marathi, Bengali, Kannada, Malayalam, Punjabi |
| **Google Maps JavaScript API** | Interactive map in the polling booth finder widget |
| **Google Places API** | Text search to locate real polling booths near user's address |
| **Google Cloud Run** | Containerized serverless deployment |

---

## Project Structure

```
civicquest/
├── app.py              # Flask routes
├── game_engine.py      # Quest definitions, state, scoring logic
├── gemini_client.py    # Gemini API wrapper (generate + chat)
├── requirements.txt
├── Dockerfile
├── .env.example
├── templates/
│   └── index.html      # Complete single-page frontend
└── tests/
    └── test_quests.py  # 18 unit tests (pytest)
```

---

## Local Setup

```bash
# 1. Clone the repo
git clone https://github.com/YOUR_USERNAME/civicquest.git
cd civicquest

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set environment variables
cp .env.example .env
# Edit .env and fill in your API keys

# 4. Run locally
python app.py
# Visit http://localhost:8080
```

---

## Running Tests

```bash
pytest tests/ -v
# Expected: 18 tests pass
```

---

## Deployment to Google Cloud Run

```bash
# 1. Build and push container
gcloud builds submit --tag gcr.io/YOUR_PROJECT/civicquest

# 2. Deploy to Cloud Run
gcloud run deploy civicquest \
  --image gcr.io/YOUR_PROJECT/civicquest \
  --platform managed \
  --region asia-south1 \
  --allow-unauthenticated \
  --set-env-vars GEMINI_API_KEY=your_key,GOOGLE_MAPS_API_KEY=your_key

# 3. Get your deployment URL
gcloud run services describe civicquest --region asia-south1 --format='value(status.url)'
```

---

## Built With

Built using **Google Antigravity** — intent-driven, agentic development.
No manual line-by-line coding. The entire project was built by prompting the
Antigravity agent with high-level objectives.

---

## License

MIT

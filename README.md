<p align="center">
  <img src="front-end-flutter/mobile/assets/logo/app_lockup.png" alt="Get To The Points" height="88">
</p>

<p align="center">
  A walking and running game set on NTHU's campus.<br>
  Walk to earn points, capture support cards, and level up through the story.
</p>

<p align="center">
  <a href="https://github.com/mobslayer62/get-to-the-points/releases/latest"><b>Download the latest Android APK</b></a>
</p>

---

## About

Students rarely have time to exercise, and usually stop because there's no
long-term reward. **Get To The Points** turns everyday walks between classes
into progress in a game, inspired by the support cards of *Umamusume: Pretty
Derby* and the real-world movement of *Pokémon GO*.

Final project for **Introduction to Programming (I2P)** at National Tsing Hua
University.

## How the game works

**Walk / run → Points → Capture cards → Equip 4 → Bonus points on the next run → Level up → Story**

Better cards earn more points per walk, which buys more cards and levels.

- **Track a walk or run.** GPS and the step counter measure the distance.
  Every 100 m earns 10 points.
- **Capture support cards.** Spend points on cards of campus landmarks:
  20 points for one, 180 for ten. Rarities are A (80%), A+ (18%) and S (2%);
  50 captures in a row without an S guarantee one, and a ×10 capture always
  includes at least one A+.
- **Equip up to 4 cards.** Each card has its own bonus (walking, running, flat
  points, distance milestones, …), so the cards you pick are your strategy.
- **Level up** (levels 1–5) to unlock **story chapters**, which follow a new
  international student's first weeks at NTHU.
- Points are shared between captures and level-ups, so every walk is a choice:
  stronger cards now, or the next chapter?

New players get an interactive tutorial and a free starter card.

## Features

| | |
|---|---|
| Distance tracking | GPS + step counter, with a filter that ignores GPS drift (standing still earns nothing) |
| Server-side rules | The server measures each run from its GPS points and checks speed, distance and duration limits |
| Capture | 10 NTHU support cards, odds and pity counter |
| Card loadout | 4 slots; bonuses itemised after every run |
| Levels and story | 5 levels, 3 written chapters, visual-novel reader |
| Accounts | Register and log in; progress is saved online |
| Tutorial | Step-by-step guided first run |

## Tech stack

| Part | Built with |
|---|---|
| Phone app | Flutter (Dart): `geolocator`, `pedometer`, `permission_handler`, `http`, `uuid` |
| Server | Python, Django 6 + Django REST Framework, token login |
| Database | SQLite (through Django's models) |
| Hosting | PythonAnywhere (HTTPS) |

All game rules (points, distance filtering, anti-cheat, capture odds, card
bonuses, levels, story) run in Python on the server. The app only displays
results, so a modified app can't change the rules.

## Project layout

```
backend/                     Django server
  Mainprogram/               settings and root URLs
  Database/
    models.py                players, runs, cards, loadouts, story progress
    views.py, urls.py        the REST API
    utils.py                 points, anti-cheat, card bonuses
    gps_distance.py          turns raw GPS points into a distance
    gacha.py                 capture odds and pity
    progression.py           levels and story unlocking
    story_chapters.py        the story text (simple script format)
    story_script.py          parses and checks the story scripts
    onboarding.py            starter card, tutorial rewards
    tests.py                 automated tests
  deploy/                    PythonAnywhere setup and update script
front-end-flutter/mobile/    Flutter app
  lib/                       screens and API client
  assets/logo/               app logo
```

## Running it locally

### Server

Needs Python 3.13 or newer.

```bash
cd backend
python -m venv venv
venv\Scripts\activate            # Windows (macOS/Linux: source venv/bin/activate)
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```

### App

Needs Flutter and an Android phone with USB debugging on.

```bash
cd front-end-flutter/mobile
flutter pub get

# against the online server
flutter run --dart-define=API_BASE_URL=https://mobslayer62.pythonanywhere.com/api

# against the server on your computer, phone connected by USB
adb reverse tcp:8000 tcp:8000
flutter run --dart-define=API_BASE_URL=http://127.0.0.1:8000/api
```

Build an installable APK:

```bash
flutter build apk --release --dart-define=API_BASE_URL=https://mobslayer62.pythonanywhere.com/api
```

## Tests

```bash
cd backend
python manage.py test
```

The tests cover points, anti-cheat limits, GPS distance filtering (with
simulated GPS noise), capture odds and pity, card bonuses, levels, the story
and the tutorial.

## Deployment

The server runs on PythonAnywhere. First-time setup and updates are described
in [`backend/deploy/README.md`](backend/deploy/README.md). To update after
merging to `main`, run `backend/deploy/update.sh` in a PythonAnywhere Bash
console and press **Reload** on the Web tab.

## API

All endpoints are under `/api/`. Everything except register and login needs
the header `Authorization: Token <token>`.

| Endpoint | Method | What it does |
|---|---|---|
| `register/`, `login/`, `logout/` | POST | Accounts; register and login return a token |
| `start-session/` | POST | Start a run and lock in the equipped cards |
| `finish-session/` | POST | Save a run (with its GPS points) and award points |
| `activity-history/`, `player-stats/` | GET | Past runs and totals |
| `home/` | GET | Main menu summary |
| `card-storage/` | GET | Owned cards |
| `equipped-cards/` | GET, POST | View or change the 4-card loadout |
| `gacha/`, `gacha/pull/` | GET, POST | Capture info and capturing cards |
| `level/`, `level/up/` | GET, POST | Level info and levelling up |
| `story/`, `story/<id>/`, `story/<id>/complete/` | GET, GET, POST | Chapters, reading, completing |
| `tutorial/`, `tutorial/run-bonus/` | GET, POST | Tutorial steps and its one-time bonus |

## Team

| | Role |
|---|---|
| **Daniel** ([@mobslayer62](https://github.com/mobslayer62)) | Backend, deployment, app screens and integration |
| **Matthew** ([@mcp2x](https://github.com/mcp2x)) | Game rules, support cards and card screens |

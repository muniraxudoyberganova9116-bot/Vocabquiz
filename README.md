# Vocabquiz

A Django-based vocabulary learning web app built around SAT/GRE-style word lists. Users register, study flashcards organized into units, take quizzes, earn XP, and compete on a leaderboard.

## Purpose

Help learners memorize vocabulary through spaced practice and gamification. Words are grouped into themed **Units**; each unit has a flashcard study mode and a quiz mode. Progress and accuracy are tracked per user, and an XP/ranking system encourages repeated practice.

## Functionalities

- **Authentication** — register, log in, and log out (Django's built-in auth).
- **Unit Hub** — landing page after login showing all units, per-unit completion status, and overall completion percentage.
- **Flashcards** — browse word/definition cards for a given unit.
- **Quizzes** — mixed-format quiz per unit combining:
  - Multiple-choice questions (pick the correct definition)
  - Matching questions (match words to definitions)
- **Scoring & progress**
  - A unit is marked **completed** when accuracy ≥ 80%.
  - XP is awarded only when a user beats their previous best on a unit (prevents replay farming), scaled to the improvement delta.
  - `words_mastered` increments the first time a unit is completed.
- **Leaderboard** — top 10 users by total XP, with a "points to top 3" hint for the current user.

## Data Model

- `Unit` — titled group of flashcards with an auto-generated slug.
- `Flashcard` — `word` + `definition`, belongs to a unit.
- `Profile` — extends `User` with `total_score` and `words_mastered`.
- `UnitProgress` — per-user, per-unit `is_completed` flag and best `accuracy`.

## Seeded Quizzes

Two seed scripts populate the database with starter content:

### `populate_db_units.py`
Seeds two SAT-style units:

- **Unit 1** — erratic, secluded, fluctuate, exalt, admonish, abrupt, content, eccentric, mired, colloquial
- **Unit 2** — reconcile, alienate, distinguish, adequate, contend, skeptical, enfranchise, sophisticated, radical, formulate

### `populate_db.py`
Seeds GRE-style units, starting with **Essential GRE Verbs** (mitigate, mollify, obfuscate, placate, repudiate, …).

Run a seed script with:

```bash
python populate_db_units.py
# or
python populate_db.py
```

## Running Locally

```bash
pip install -r requirements.txt
python manage.py migrate
python populate_db_units.py
python manage.py runserver
```

Then visit `http://127.0.0.1:8000/`.

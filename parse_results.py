#!/usr/bin/env python3
"""
Parses all iRacing event result JSONs from the results/ folder
and generates docs/data/races.json automatically.
"""

import json
import os
import glob
from datetime import datetime, timezone

RESULTS_DIR = "results"
OUTPUT_FILE = "docs/data/races.json"
SEASON_YEAR = "2026"

def parse_result(filepath):
    with open(filepath) as f:
        data = json.load(f)

    d = data['data']

    # Track info
    track = d['track']
    track_name = track['track_name']
    config = track.get('config_name', '')
    track_display = f"{track_name} - {config}" if config else track_name

    # Date
    start_time = d.get('start_time', '')
    try:
        date = datetime.fromisoformat(start_time.replace('Z', '+00:00')).strftime('%Y-%m-%d')
    except:
        date = "1970-01-01"

    # Car name
    car_name = "Formula Vee"
    for session in d.get('session_results', []):
        for r in session.get('results', []):
            if r.get('car_name'):
                car_name = r['car_name']
                break
        break

    # Find race session
    race_session = None
    for session in d.get('session_results', []):
        name = session.get('simsession_name', '')
        if name in ('RACE', 'FEATURE'):
            race_session = session
            break

    if not race_session:
        print(f"  WARNING: No race session found in {filepath}, skipping.")
        return None

    results = sorted(race_session['results'], key=lambda r: r['finish_position'])

    # Fastest lap
    valid_laps = [r['best_lap_time'] for r in results if r.get('best_lap_time', -1) > 0]
    min_lap = min(valid_laps) if valid_laps else -1

    race_results = []
    for r in results:
        dnf = r.get('reason_out', 'Running') != 'Running'
        fl = min_lap > 0 and r.get('best_lap_time') == min_lap
        race_results.append({
            "driver": r['display_name'],
            "finish": r['finish_position'] + 1,
            "start": r['starting_position'] + 1,
            "fastest_lap": fl,
            "incidents": r.get('incidents', 0),
            "dnf": dnf
        })

    # Use subsession_id as stable unique ID
    subsession_id = d.get('subsession_id', 0)

    return {
        "_subsession_id": subsession_id,
        "_date": date,
        "track": track_display,
        "car": car_name,
        "date": date,
        "results": race_results
    }


def main():
    files = glob.glob(os.path.join(RESULTS_DIR, "eventresult-*.json"))

    if not files:
        print(f"No result files found in {RESULTS_DIR}/")
        return

    print(f"Found {len(files)} result file(s)...")

    parsed = []
    for f in files:
        print(f"  Parsing {os.path.basename(f)}...")
        result = parse_result(f)
        if result:
            parsed.append(result)

    # Sort by date ascending
    parsed.sort(key=lambda r: r['_date'])

    # Assign sequential IDs based on date order
    races = []
    for i, r in enumerate(parsed):
        races.append({
            "id": i + 1,
            "date": r["date"],
            "track": r["track"],
            "car": r["car"],
            "results": r["results"]
        })

    output = {
        "season": SEASON_YEAR,
        "races": races
    }

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"\nDone! Generated {OUTPUT_FILE} with {len(races)} race(s).")
    for r in races:
        print(f"  Race {r['id']}: {r['track']} ({r['date']}) — {len(r['results'])} drivers")


if __name__ == "__main__":
    main()

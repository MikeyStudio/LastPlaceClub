#!/usr/bin/env python3
"""
Parses all iRacing event result JSONs from results/season-*/ folders
and generates one docs/data/races-season-N.json per season, plus a
docs/data/seasons.json manifest listing the available seasons.
"""

import json
import os
import re
import glob
from datetime import datetime, timezone

RESULTS_DIR = "results"
OUTPUT_DIR = "docs/data"

SEASON_DIR_RE = re.compile(r"^season-(\d+)$")


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


def find_season_dirs():
    """Return sorted list of (season_number, dir_path) for results/season-N/ folders."""
    seasons = []
    if not os.path.isdir(RESULTS_DIR):
        return seasons
    for entry in os.listdir(RESULTS_DIR):
        full = os.path.join(RESULTS_DIR, entry)
        if not os.path.isdir(full):
            continue
        m = SEASON_DIR_RE.match(entry)
        if m:
            seasons.append((int(m.group(1)), full))
    seasons.sort(key=lambda s: s[0])
    return seasons


def parse_season(season_num, season_dir):
    files = glob.glob(os.path.join(season_dir, "eventresult-*.json"))

    parsed = []
    for f in files:
        print(f"  Parsing {os.path.basename(f)}...")
        result = parse_result(f)
        if result:
            parsed.append(result)

    # Sort by date ascending, assign sequential IDs
    parsed.sort(key=lambda r: r['_date'])

    races = []
    for i, r in enumerate(parsed):
        races.append({
            "id": i + 1,
            "date": r["date"],
            "track": r["track"],
            "car": r["car"],
            "results": r["results"]
        })

    return {
        "season": season_num,
        "label": f"Season {season_num}",
        "races": races
    }


def main():
    season_dirs = find_season_dirs()

    if not season_dirs:
        print(f"No season folders found in {RESULTS_DIR}/ (expected results/season-1, results/season-2, ...)")
        return

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    manifest = {"seasons": []}

    for season_num, season_dir in season_dirs:
        print(f"Season {season_num}: scanning {season_dir}...")
        season_data = parse_season(season_num, season_dir)

        out_file = f"races-season-{season_num}.json"
        out_path = os.path.join(OUTPUT_DIR, out_file)
        with open(out_path, 'w') as f:
            json.dump(season_data, f, indent=2)

        race_count = len(season_data["races"])
        print(f"  -> {out_path} ({race_count} race(s))")

        manifest["seasons"].append({
            "id": f"season-{season_num}",
            "label": season_data["label"],
            "file": out_file,
            "raceCount": race_count
        })

    manifest_path = os.path.join(OUTPUT_DIR, "seasons.json")
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)

    print(f"\nDone! Wrote {manifest_path} with {len(manifest['seasons'])} season(s).")


if __name__ == "__main__":
    main()

# Glide — GBFS scooter browser

A small local Linux app that displays Dott vehicles from its public GBFS feed. It is a vehicle finder prototype; rentals and unlocking require operator partner access.

## Run

Requires Python 3.11+ and an internet connection for the live GBFS feed and Google Maps. The app loads Qick's Maps API key from `map_keys.txt` when serving the page.

```sh
cd ~/gbfs
python3 app.py
```

Open <http://127.0.0.1:8811>. Press `Ctrl+C` in the terminal to stop it. The app refreshes vehicle data every minute.

The app reads Dott's public GBFS discovery feed at `https://gbfs.api.ridedott.com/public/v2/gbfs.json`.

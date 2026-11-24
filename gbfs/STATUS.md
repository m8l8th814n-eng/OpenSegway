# Projektstatus och överlämning

Senast uppdaterad: 2026-10-31

## Mål

Bygga en Linux-vänlig app som visar tillgängliga elsparkcyklar på en karta med data från GBFS. Nuvarande datakälla är Dott:s publika GBFS-flöde. Appen visar fordon och status; uthyrning/upplåsning ingår inte och skulle kräva operatörens partner-API.

## Filer och körning

- `app.py` – lokal Python HTTP-server och GBFS-klient.
- `static/index.html` – kartgränssnitt, fordonslista, ID-sökning och automatisk uppdatering varje minut.
- `map_keys.txt` – lokalt tillhandahållna Google Maps-nycklar; nycklarna ska inte kopieras till dokumentation eller checkas in.
- `README.md` – grundläggande installations- och körinstruktioner.

Starta från terminalen:

```sh
cd ~/gbfs
python3 app.py
```

Öppna `http://127.0.0.1:8811`.

## Nuvarande kartläge

Kartmotorn är Google Maps JavaScript API. `app.py` läser för närvarande Qick-nyckeln från `map_keys.txt` och injicerar den när HTML-sidan skickas till webbläsaren. Kartan laddas, men Google visar vattenstämpeln **“For development purposes only”**. Det betyder att nyckeln/projektet inte är godkänt för vanlig användning, ofta på grund av API-behörighet eller fakturering. Appen har inte verifierats med en egen nyckel.

## Nästa steg

Välj en av följande lösningar för kartan:

1. Skapa och använd en egen Google Maps-nyckel, aktivera Maps JavaScript API och konfigurera fakturering samt tillåt lokal webbplats (`localhost`/`127.0.0.1`). Ändra sedan nyckelvalet i `app.py` så det inte använder en nyckel från en annan aktörs Android-app.
2. Byt till en öppen kartmotor/tileserver som inte behöver Google Maps API-nyckel.

Efter ändring av nyckeln startas servern om med `Ctrl+C` och `python3 app.py`, och sidan laddas om i webbläsaren.

## Viktigt att känna till

- `map_keys.txt` innehåller API-nycklar. Bevara filen lokalt och publicera inte dess innehåll.
- Google-nyckeln skickas till webbläsaren eftersom Google Maps JavaScript API kör klientbaserat; använd en egen nyckel med webbplats- och API-begränsningar.
- Själva GBFS-flödet kan vara beroende av internet och Dott kan ändra eller begränsa det.

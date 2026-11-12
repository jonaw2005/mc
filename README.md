# Minecraft-Server mit Versionsauswahl

Installation eines **Minecraft Java Edition Vanilla**-Servers als Docker-Container.
Kein Bedrock, Paper, Forge oder Fabric. Die Versionsliste kommt bei jedem Aufruf
aus Mojangs offiziellem Manifest. Python verwendet ausschliesslich die Standardbibliothek.

## Installation auf dem Server

Repository nach `/opt/minecraft/server` klonen. Danach:

```bash
cd /opt/minecraft/server
sudo bash /opt/minecraft/server/install.sh
```

Das Skript bietet Releases seitenweise zur Auswahl an. Nummer oder exakte
Versions-ID eingeben; `n`/`p` wechseln die Seite, `q` bricht ab.
Danach die Minecraft-EULA lesen und mit `ja` bestaetigen. Der Container wird
heruntergeladen, gestartet und bis zu 300 Sekunden auf seinen Healthcheck gewartet.
Bei einem Timeout kann er noch starten: Logs kontrollieren.

Auf nativem Debian/Ubuntu mit apt und systemd kann das Skript nach Rueckfrage
fehlende Werkzeuge und Docker aus dem offiziellen Docker-Repository installieren.
Die Distribution muss vom Docker-Repository unterstuetzt werden. Konfliktpakete
werden nicht entfernt, bestehende Docker-Paketquellen nicht ueberschrieben.
Auf anderen Linux-Systemen Docker Engine, Compose v2, Python 3 (>= 3.8), curl
und CA-Zertifikate vorher selbst installieren. Internetzugang ist erforderlich.

Die Java-Zuordnung unterstuetzt Java 8, 16 (mit Java-17-Image), 17, 21 und 25.
Andere Java-Anforderungen werden bewusst abgelehnt. Historische Versionen ohne
offiziellen Server-Download werden ebenfalls abgelehnt. Nicht jede historische
Version wurde praktisch getestet. Fuer moderne Versionen einen 64-Bit-Host verwenden.

## Optionen

Bestimmte Version mit 4 GiB Java-Heap (keine Begrenzung des gesamten Container-RAM):

```bash
sudo bash /opt/minecraft/server/install.sh --version 1.21.1 --memory 4G
```

Auch Snapshots in der Auswahl anbieten:

```bash
sudo bash /opt/minecraft/server/install.sh --snapshots
```

Konfiguration ohne Containerstart erstellen:

```bash
sudo bash /opt/minecraft/server/install.sh --version 1.21.1 --configure-only
```

`--configure-only` verhindert den Containerstart, nicht die vorherige Pruefung
der Systemvoraussetzungen. Fuer reine Konfiguration bei vorhandenem Python:

```bash
python3 /opt/minecraft/server/scripts/install.py --version 1.21.1 --configure-only
```

Weitere Optionen: `--port 25566`, `--bind 127.0.0.1`, `--accept-eula`.
Mit `--accept-eula` erklaerst du ausdruecklich deine Zustimmung zur Minecraft-EULA;
es ist kein automatischer Standard. Ohne Versionsparameter ist ein Terminal erforderlich.
Bei bereits eingerichteten Voraussetzungen ist die Installation mit `--version`
und `--accept-eula` ohne Eingabe moeglich.

## Daten und Versionswechsel

- `/opt/minecraft/server/.env`: ausgewaehlte Version, Java-Tag, RAM, Port, EULA.
- `/opt/minecraft/server/data/<version>/`: Welt, Einstellungen, Spielerdaten.
- `/opt/minecraft/server/compose.yml`: Container-Konfiguration.
- Weltdaten und lokale Konfiguration sind von Git ausgeschlossen.

Installationsskript erneut ausfuehren, um eine andere Version auszuwaehlen.
**Jede Version hat absichtlich eigene Daten.** Ein Wechsel erstellt eine neue Welt
oder verwendet die bereits vorhandene Welt dieser Version. Es laeuft jeweils nur
eine Version. Keine automatische Weltmigration und kein automatischer Downgrade!
Fuer eine bewusste Migration erst stoppen, sichern und Kompatibilitaet pruefen.

Ein erneuter Installer-Aufruf setzt RAM, Port und Bind-Adresse auf die angegebenen
Werte bzw. die Standards `2G`, `25565`, `0.0.0.0`. Eigene Werte erneut angeben.
Minecraft bleibt auf der ausgewaehlten Version. Java-Image-Tags sind beweglich;
ein erneuter Installer-Aufruf kann ein neueres Container-Image herunterladen.
Bei einem Fehler nach dem Schreiben bleibt die neue `.env` bestehen; ein bisheriger
Container kann noch mit seiner alten Konfiguration laufen. Logs und Status pruefen.

## Betrieb

Alle folgenden Befehle im Projektverzeichnis ausfuehren:

```bash
cd /opt/minecraft/server
sudo docker compose ps
sudo docker compose logs -f --tail=100
sudo docker compose stop
sudo docker compose start
sudo docker compose restart
```

Nach manueller Aenderung der `.env` die Konfiguration mit
`sudo docker compose up -d` anwenden; `restart` allein reicht dafuer nicht.
Der Container hat die Restart-Policy `unless-stopped` und startet bei aktivem
Docker-Dienst nach einem Host-Neustart, sofern er nicht absichtlich gestoppt wurde.
Servereinstellungen in `/opt/minecraft/server/data/<version>/server.properties`
bei gestopptem Server aendern; vom Compose-Environment verwaltete Werte dort nicht
widerspruechlich konfigurieren. Der interne Serverport bleibt 25565.

### Backup

Konsistente Sicherung mit gestopptem Server (bei Fehlern nicht einfach fortfahren):

```bash
cd /opt/minecraft/server
sudo mkdir -p /opt/minecraft/server/backups
sudo docker compose stop && sudo tar -czf "/opt/minecraft/server/backups/minecraft-$(date +%Y%m%d-%H%M%S).tar.gz" .env data && sudo docker compose start
```

Backups zusaetzlich ausserhalb dieses Servers aufbewahren. Zur Wiederherstellung
Container stoppen und das Archiv zuerst in ein separates Verzeichnis entpacken;
Konfiguration und passende Versionsdaten gezielt zurueckspielen.

## Netzwerk und Sicherheit

Standardmaessig wird TCP 25565 auf allen IPv4-Schnittstellen veroeffentlicht.
Im Client `SERVER-IP:25565` eintragen und dieselbe Minecraft-Version verwenden.
Provider-Firewall und gegebenenfalls Router gezielt konfigurieren. Docker-Portfreigaben
koennen UFW-Regeln umgehen; nicht allein auf UFW verlassen. Fuer lokalen Zugriff
`--bind 127.0.0.1` verwenden. Das Skript aendert keine Firewallregeln.
Online-Authentifizierung ist eingeschaltet, RCON ausgeschaltet. Fuer einen privaten
Server nach dem ersten Start stoppen und `white-list=true` in der passenden
`server.properties` sowie die erlaubten Profile in `whitelist.json` konfigurieren.
Der Host braucht zusaetzlich zum Java-Heap freien RAM fuer JVM, Container und Betriebssystem.

## Tests

```bash
cd /opt/minecraft/server
python3 -m unittest discover -s /opt/minecraft/server/tests -v
bash -n /opt/minecraft/server/install.sh
```

Die Unit-Tests verwenden simulierte Metadaten und starten keine Container.
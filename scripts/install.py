#!/usr/bin/env python3
"""Vanilla installer; Python standard library only."""

import argparse
import ipaddress
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = 'https://piston-meta.mojang.com/mc/game/version_manifest_v2.json'
JAVA_TAGS = {8: 'java8', 16: 'java17', 17: 'java17', 21: 'java21', 25: 'java25'}


def fetch_json(url):
    if not url.startswith('https://'):
        raise ValueError('Versionsmetadaten muessen ueber HTTPS geladen werden.')
    request = urllib.request.Request(url, headers={'User-Agent': 'minecraft-repo-installer/1.0'})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def available_versions(manifest, snapshots=False):
    kinds = {'release', 'snapshot'} if snapshots else {'release'}
    return [item for item in manifest['versions'] if item['type'] in kinds]


def select_version(versions):
    page = 0
    size = 20
    while True:
        print('\nMinecraft Java Edition – Vanilla')
        for number, item in enumerate(versions[page:page + size], page + 1):
            print(f"{number:4}. {item['id']} ({item['type']})")
        answer = input('Nummer oder Versions-ID; n=weiter, p=zurueck, q=abbrechen: ').strip()
        if answer == 'q':
            raise ValueError('Installation abgebrochen.')
        if answer == 'n':
            page = page + size if page + size < len(versions) else 0
        elif answer == 'p':
            page = max(0, page - size)
        elif answer.isdigit() and 1 <= int(answer) <= len(versions):
            return versions[int(answer) - 1]
        else:
            match = next((v for v in versions if v['id'] == answer), None)
            if match:
                return match
            print('Ungueltige Auswahl.')


def java_tag(metadata):
    if 'server' not in metadata.get('downloads', {}):
        raise ValueError('Fuer diese Version ist kein offizieller Server-Download vorhanden.')
    major = metadata.get('javaVersion', {}).get('majorVersion', 8)
    if major not in JAVA_TAGS:
        raise ValueError(f'Java {major} wird noch nicht unterstuetzt. Image-Zuordnung aktualisieren.')
    return JAVA_TAGS[major]


def validate_settings(version, memory, port, bind):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', version):
        raise ValueError('Ungueltige Versions-ID.')
    if not re.fullmatch(r'[1-9][0-9]*[MG]', memory):
        raise ValueError('RAM muss z. B. 2G oder 2048M sein.')
    if not 1 <= port <= 65535:
        raise ValueError('Port muss zwischen 1 und 65535 liegen.')
    ipaddress.IPv4Address(bind)


def write_env(root, version, tag, memory, port, bind):
    validate_settings(version, memory, port, bind)
    content = (f'MC_VERSION={version}\nJAVA_TAG={tag}\nMEMORY={memory}\n'
               f'SERVER_PORT={port}\nBIND_ADDRESS={bind}\nEULA=TRUE\n')
    temporary = root / '.env.tmp'
    temporary.write_text(content, encoding='utf-8')
    temporary.chmod(0o600)
    os.replace(temporary, root / '.env')


def compose(*args):
    subprocess.run(['docker', 'compose', '--project-directory', str(ROOT),
                    '--env-file', str(ROOT / '.env'), '-f', str(ROOT / 'compose.yml'),
                    *args], check=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Minecraft Java Vanilla installieren')
    parser.add_argument('--version', help='Exakte Minecraft-Version, sonst interaktive Auswahl')
    parser.add_argument('--snapshots', action='store_true', help='Auch Entwicklungsversionen anzeigen')
    parser.add_argument('--accept-eula', action='store_true', help='Minecraft-EULA ausdruecklich akzeptieren')
    parser.add_argument('--memory', default='2G', help='Java-Heap, Standard: 2G')
    parser.add_argument('--port', type=int, default=25565)
    parser.add_argument('--bind', default='0.0.0.0', help='IPv4-Bind-Adresse')
    parser.add_argument('--configure-only', action='store_true', help='Konfiguration schreiben, nicht starten')
    args = parser.parse_args(argv)
    validate_settings(args.version or 'selection', args.memory, args.port, args.bind)
    versions = available_versions(fetch_json(MANIFEST), args.snapshots)
    if args.version:
        selected = next((v for v in versions if v['id'] == args.version), None)
        if selected is None:
            raise ValueError('Version nicht gefunden. Fuer Snapshots --snapshots angeben.')
    else:
        selected = select_version(versions)
    version = selected['id']
    validate_settings(version, args.memory, args.port, args.bind)
    metadata = fetch_json(selected['url'])
    if metadata['id'] != version:
        raise ValueError('Versionsmetadaten passen nicht zur Auswahl.')
    tag = java_tag(metadata)
    print(f'\nVersion: {version}; Java-Image: {tag}; RAM: {args.memory}')
    print(f'Daten: {ROOT / "data" / version}')
    print(f'Port: {args.bind}:{args.port}; RCON deaktiviert; Online-Authentifizierung aktiv.')
    print('Jede Version verwendet eine eigene Welt. Vor Aenderungen bestehende Daten sichern!')
    if not args.accept_eula:
        print('Minecraft-EULA: https://www.minecraft.net/eula')
        if input('EULA gelesen und akzeptiert? [ja/NEIN]: ').strip().lower() != 'ja':
            raise ValueError('Ohne EULA-Zustimmung wird keine Konfiguration geschrieben.')
    write_env(ROOT, version, tag, args.memory, args.port, args.bind)
    if args.configure_only:
        print('Konfiguration gespeichert. Ein laufender Container wurde nicht geaendert.')
        return
    compose('config', '--quiet')
    compose('pull')
    compose('up', '-d', '--wait', '--wait-timeout', '300')
    print('Server ist gestartet und laut Docker-Healthcheck bereit.')
    print(f'Logs: cd {ROOT} && sudo docker compose logs -f --tail=100')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, OSError, urllib.error.URLError, subprocess.CalledProcessError) as error:
        print(f'Fehler: {error}', file=sys.stderr)
        print('Bei Startproblemen: sudo docker compose logs --tail=100', file=sys.stderr)
        sys.exit(1)
    except (KeyboardInterrupt, EOFError):
        print('\nInstallation abgebrochen.', file=sys.stderr)
        sys.exit(130)
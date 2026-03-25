"""
Parser pour les fichiers .dbz1 (Elan Cité / Evocom — Radar Pédagogique)

Structure du fichier .dbz1 :
  Un fichier = N blocs journaliers consécutifs.
  Chaque bloc :
    - 4 octets     : uint32 BE = longueur de la chaîne filename
    - N octets     : UTF-16 BE = chemin interne ex. "/20240914235959.bin"
    - 2 octets     : padding  (0x0000)
    - 2 octets     : uint16 BE = valeur inconnue (~taille totale du bloc externe)
    - 2 octets     : padding  (0x0000)
    - 2 octets     : uint16 BE = taille décompressée du contenu
    - Reste        : données compressées zlib (fin = détectée par unused_data)

  Données décompressées de chaque bloc :
    - 4 octets     : magic 0xA0B0C0D0
    - Bloc header  : chaînes UTF-16 BE (commune, MAC, OS, firmware…)
    - Enregistrements de 8 octets chacun :
        0xFFFD (séparateur, 2o)
        + slot_temps (uint16 BE, 2o)   → slot × 10 min = minutes depuis minuit
        + vitesse_limite (uint16 BE, 2o) → km/h, constante par fichier
        + vitesse_mesurée (uint16 BE, 2o) → km/h détectée
"""

import struct
import zlib
from dataclasses import dataclass, field
from datetime import date, time
from pathlib import Path
from typing import Optional
import re


# ---------------------------------------------------------------------------
# Structures de données
# ---------------------------------------------------------------------------

@dataclass
class RadarRecord:
    """Un passage de véhicule détecté par le radar."""
    recording_date: date
    time_slot: int      # slot × 10 min = minutes depuis minuit
    speed_limit: int    # km/h
    speed: int          # km/h mesuré

    @property
    def slot_minutes(self) -> int:
        return self.time_slot * 10

    @property
    def slot_time(self) -> time:
        total = self.slot_minutes
        h = min(total // 60, 23)
        m = total % 60
        return time(hour=h, minute=m)

    @property
    def over_limit(self) -> bool:
        return self.speed > self.speed_limit

    @property
    def excess(self) -> int:
        """Excès de vitesse en km/h (0 si dans les limites)."""
        return max(0, self.speed - self.speed_limit)


@dataclass
class RadarDeviceInfo:
    """Informations du dispositif radar (extraites du premier bloc)."""
    device_id: str = ""     # MAC / identifiant matériel
    commune: str = ""       # Nom de la commune
    os_info: str = ""       # Système d'exploitation embarqué
    firmware: str = ""      # Version du firmware


@dataclass
class RadarDataset:
    """Jeu de données complet extrait d'un fichier .dbz1."""
    source_file: str
    device: RadarDeviceInfo
    records: list[RadarRecord] = field(default_factory=list)
    daily_record_counts: dict = field(default_factory=dict)  # date → int

    # --- Propriétés calculées ---

    @property
    def total_detections(self) -> int:
        return len(self.records)

    @property
    def date_range(self) -> tuple[Optional[date], Optional[date]]:
        if not self.records:
            return None, None
        dates = [r.recording_date for r in self.records]
        return min(dates), max(dates)

    @property
    def speed_limit(self) -> Optional[int]:
        if self.records:
            return self.records[0].speed_limit
        return None

    @property
    def avg_speed(self) -> Optional[float]:
        if not self.records:
            return None
        return sum(r.speed for r in self.records) / len(self.records)

    @property
    def max_speed(self) -> Optional[int]:
        if not self.records:
            return None
        return max(r.speed for r in self.records)

    @property
    def pct_over_limit(self) -> Optional[float]:
        if not self.records:
            return None
        over = sum(1 for r in self.records if r.over_limit)
        return over / len(self.records) * 100

    @property
    def unique_days(self) -> int:
        return len(set(r.recording_date for r in self.records))


# ---------------------------------------------------------------------------
# Parsing interne
# ---------------------------------------------------------------------------

def _parse_date_from_path(path_str: str) -> Optional[date]:
    """Extrait la date depuis une chaîne du type /20240914235959.bin"""
    m = re.search(r"(\d{4})(\d{2})(\d{2})", path_str)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    return None


def _extract_tlv_strings_utf16le(data: bytes, end: int) -> list[str]:
    """
    Extrait les chaînes du bloc header en format TLV (UTF-16 LE).
    Format TLV : uint16 LE (longueur en octets) + N octets UTF-16 LE + uint16 00 00.
    Commence après le magic (4 bytes) et les 4 octets de méta initiaux.
    """
    results = []
    pos = 8  # magic(4) + uint32_inconnu(4)
    while pos + 4 < end:
        try:
            ln = struct.unpack('<H', data[pos:pos+2])[0]
        except struct.error:
            break
        if ln == 0 or ln > 256 or pos + 2 + ln + 2 > end:
            pos += 2
            continue
        raw_str = data[pos+2:pos+2+ln]
        null_term = data[pos+2+ln:pos+2+ln+2]
        if null_term == b'\x00\x00':
            try:
                s = raw_str.decode('utf-16-le', errors='replace').strip()
                if s:
                    results.append(s)
            except Exception:
                pass
            pos = pos + 2 + ln + 2
        else:
            pos += 2
    return results


def _identify_header_strings(strings: list[str]) -> dict:
    """Classe les chaînes du header en champs nommés."""
    meta = {}
    for s in strings:
        s = s.strip()
        if not s:
            continue
        if s.startswith('Q_OS_'):
            meta['os'] = s
        elif len(s) == 12 and re.fullmatch(r'[0-9A-Fa-f]+', s):
            meta['device_id'] = s.upper()
        elif re.match(r'\d+\.\d+', s) and len(s) <= 20:
            # Extraire uniquement la partie numérique (artefact possible en fin de version)
            clean = re.match(r'[\d.]+', s).group(0).strip('.')
            if clean:
                meta['firmware'] = clean
        elif s in ('inconnu', 'unknown', 'NULL') or s.startswith('inconnu'):
            pass
        elif s.startswith('OK-') or s.startswith('STATS') or s.startswith('GET'):
            pass  # messages de protocole, ignorés
        elif s.isdigit() and len(s) <= 6:
            pass  # codes numériques, ignorés
        elif 'commune' not in meta and len(s) >= 3 and not s.startswith('/'):
            meta['commune'] = s
    return meta


def _parse_block_records(decompressed: bytes, recording_date: Optional[date]) -> list[RadarRecord]:
    """
    Extrait les enregistrements d'un bloc décompressé.
    Chaque enregistrement = 8 octets alignés sur 0xFFFD.
    """
    if len(decompressed) < 4 or decompressed[:4] != b'\xa0\xb0\xc0\xd0':
        return []

    first_fffd = decompressed.find(b'\xff\xfd')
    if first_fffd == -1:
        return []

    records = []
    d = recording_date or date(1970, 1, 1)
    i = first_fffd
    while i + 8 <= len(decompressed):
        if decompressed[i:i+2] == b'\xff\xfd':
            v1 = struct.unpack('>H', decompressed[i+2:i+4])[0]
            v2 = struct.unpack('>H', decompressed[i+4:i+6])[0]
            v3 = struct.unpack('>H', decompressed[i+6:i+8])[0]
            # Filtrer les enregistrements corrompus (champ = séparateur)
            if v1 != 0xFFFD and v2 != 0xFFFD and v3 != 0xFFFD:
                # v1 = slot_temps (tranche × 10 min depuis minuit)
                # v2 = seuil configuré (constante, ex. 64 km/h)
                # v3 = vitesse mesurée (km/h, toujours > seuil)
                records.append(RadarRecord(
                    recording_date=d,
                    time_slot=v1,
                    speed_limit=v2,
                    speed=v3,
                ))
            i += 8
        else:
            i += 2
    return records


def _parse_block_device_info(decompressed: bytes) -> dict:
    """Extrait les infos du dispositif depuis le header d'un bloc décompressé."""
    if len(decompressed) < 4 or decompressed[:4] != b'\xa0\xb0\xc0\xd0':
        return {}
    first_fffd = decompressed.find(b'\xff\xfd')
    end = first_fffd if first_fffd != -1 else len(decompressed)
    strings = _extract_tlv_strings_utf16le(decompressed, end)
    return _identify_header_strings(strings)


# ---------------------------------------------------------------------------
# API publique
# ---------------------------------------------------------------------------

def _find_zlib_magic(data: bytes, start: int) -> Optional[int]:
    """Retourne l'offset du premier magic zlib à partir de start (dans une fenêtre de 32 octets)."""
    for o in range(start, min(start + 32, len(data) - 1)):
        if data[o] == 0x78 and data[o + 1] in (0x01, 0x5E, 0x9C, 0xDA):
            return o
    return None


def parse_dbz1(source, progress_callback=None) -> RadarDataset:
    """
    Parse un fichier .dbz1 complet (potentiellement des centaines de blocs journaliers).

    :param source:            chemin (str | Path) ou bytes du fichier brut
    :param progress_callback: callable(current_block, total_est) appelé à chaque bloc (optionnel)
    :return:                  RadarDataset complet
    :raises ValueError:       si le format est invalide
    """
    if isinstance(source, (str, Path)):
        source_name = str(Path(source).name)
        with open(source, 'rb') as f:
            raw = f.read()
    elif isinstance(source, (bytes, bytearray)):
        source_name = "<upload>"
        raw = bytes(source)
    else:
        source_name = "<stream>"
        raw = source.read()

    if len(raw) < 54:
        raise ValueError("Fichier trop court pour être un .dbz1 valide")

    all_records: list[RadarRecord] = []
    device_info: Optional[RadarDeviceInfo] = None
    daily_counts: dict = {}
    block_index = 0
    pos = 0

    while pos < len(raw) - 10:
        # Lire la longueur de la chaîne interne
        if pos + 4 > len(raw):
            break
        try:
            str_len = struct.unpack('>I', raw[pos:pos+4])[0]
        except struct.error:
            break

        if str_len == 0 or str_len > 512:
            break
        if pos + 4 + str_len + 8 > len(raw):
            break

        # Lire la chaîne interne
        internal_name = raw[pos+4:pos+4+str_len].decode('utf-16-be', errors='replace')
        recording_date = _parse_date_from_path(internal_name)

        # Localiser le bloc zlib
        zlib_offset = _find_zlib_magic(raw, pos + 4 + str_len)
        if zlib_offset is None:
            break

        # Décompresser
        try:
            do = zlib.decompressobj()
            decompressed = do.decompress(raw[zlib_offset:])
            consumed = len(raw) - zlib_offset - len(do.unused_data)
        except zlib.error:
            # Bloc corrompu → on avance de 4 et on réessaie
            pos += 4
            continue

        # Extraire les infos du dispositif (une seule fois, depuis le premier bloc)
        if device_info is None:
            meta = _parse_block_device_info(decompressed)
            device_info = RadarDeviceInfo(
                device_id=meta.get('device_id', ''),
                commune=meta.get('commune', ''),
                os_info=meta.get('os', ''),
                firmware=meta.get('firmware', ''),
            )

        # Parser les enregistrements du bloc
        block_records = _parse_block_records(decompressed, recording_date)
        all_records.extend(block_records)
        if recording_date:
            daily_counts[recording_date] = len(block_records)

        block_index += 1
        if progress_callback:
            progress_callback(block_index, None)

        # Passer au bloc suivant
        pos = zlib_offset + consumed

    if device_info is None:
        device_info = RadarDeviceInfo()

    return RadarDataset(
        source_file=source_name,
        device=device_info,
        records=all_records,
        daily_record_counts=daily_counts,
    )


def scan_folder(folder: str | Path) -> list[Path]:
    """Retourne la liste des fichiers .dbz1 dans un dossier (tri par date de modification, desc)."""
    folder = Path(folder)
    if not folder.exists():
        return []
    return sorted(folder.glob('**/*.dbz1'), key=lambda p: p.stat().st_mtime, reverse=True)

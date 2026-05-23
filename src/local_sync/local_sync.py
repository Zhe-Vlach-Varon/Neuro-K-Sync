import argparse
import io
import logging
import os
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import cast

import hjson
import requests
from metadata_utils.CF_Program import Song, process_new_tags, set_tags_fast
from metadata_utils.create_hjsons import create_payload_from_dict
from metadata_utils.engraver import engrave_payload, get_all_mp3, get_raw_json
from metadata_utils.hash_mutagen import get_audio_hash

from .DF_Customizer.file_manager import FileManager
from .DF_formatter import apply_in_background, load_preset

logger = logging.getLogger(__name__)

def format_tags(file_path: str, script_dir: Path, song_obj: Song, preset: dict[str, list[dict[str, str]]] | None) -> None:
    if not DF_format(file_path, script_dir, preset):
        set_tags_fast(file_path, song_obj, None, None)

def DF_format (file_path: str, script_dir: Path, preset: dict[str, list[dict[str, str]]] | None) -> bool:
    """
    Function for formatting a song with a DF preset
    """
    if preset is None:
        return False

    try:
        apply_in_background(file_path=file_path, fm=FileManager(), preset=preset)

    except Exception:
        logger.exception("Unable to format with preset!")
        return False

    else:
        return True

def setup_preset(script_dir: Path) -> dict[str, list[dict[str, str]]] | None:

    presets = get_all_json(script_dir)

    if not presets:
        return

    try :
        preset = load_preset(presets[0])

        if preset is None:
            return

    except Exception:
        logger.exception("Unable to load with preset!")
        return

    else:
        return preset

def get_all_json(p: Path) -> list[Path]: 
    """
    Function that gathers all JSON files from a directory.
    """
    return [(f) for f in p.rglob('*.json') if f.is_file()]

def get_remote_zip() -> io.BytesIO | None:
    url = "https://github.com/Nyss777/Neuro-Karaoke-Archive-Metadata/releases/download/latest/metadata-zip.zip"

    try:    

        response = requests.get(url)

        response.raise_for_status()

        if response.status_code == 200:
            # Wrap the bytes in a "BytesIO" object
            zip_in_memory = io.BytesIO(response.content)
            
            return zip_in_memory

    except requests.exceptions.HTTPError as err:
        status_code = err.response.status_code if err.response is not None else "Unknown"
        logger.error(f"Http Error: {status_code}")

    except requests.exceptions.ConnectionError:
        logger.exception("Error Connecting")

    except requests.exceptions.Timeout:
        logger.exception("Timeout Error")

    except requests.exceptions.RequestException:
        logger.exception("An Error Happened")

    return None

def get_metadata_from_zip(zip_ref: zipfile.ZipFile, hjson_path: str) -> dict[str, str|int|float] | None:
    # 1. Load the HJSON metadata
    try:
        with zip_ref.open(hjson_path, 'r') as f:
            content = f.read().decode('utf-8')
            metadata = cast(dict[str, str|int|float], hjson.loads(content))
        return metadata

    except Exception:
        logger.exception(f"Unable to process metadata for {os.path.basename(hjson_path)}!")
        return None

def get_songs_directory(path_config_file: Path, args: argparse.Namespace) -> Path | None:

    ### Priority list:
    # 1. args.path
    # 2. config
    # 3. window selection

    if args.path and (arg_path := Path(args.path)).is_dir():
        return arg_path

    elif path_config_file.exists():
        try:
            with open(path_config_file, 'r', encoding='utf-8') as h:
                config_content = h.read()
            if (config_path := Path(config_content)).is_dir():
                return config_path
        except PermissionError:
            logger.error("Permission Error. Unable to load path_config.txt")
    
    else:
        logger.debug("No path configuration found, loading selection window")
        selected = folder_selection_dialog()
        if selected is not None and (selected_path := Path(selected)).is_dir():
            return selected_path
            
    return None

def folder_selection_dialog() -> str | None:

    """Opens a file selection dialog and returns the selected file path."""
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()

        folder_path = filedialog.askdirectory(
            title="Select the Neuro songs location",
            initialdir=os.getcwd()
        )

        root.destroy()

        if folder_path:
            logger.debug(f"Selected folder path: {folder_path}")
            return folder_path
        else:
            logger.info("No folder path selected")

    except ImportError:
        logger.critical("\nGUI selection unavailable (Tkinter not found).\n Please pass the path as an argument!")
        return None

def save_path(path_config_file: Path, directory: Path) -> None:
    try:
        if Path(path_config_file).exists():
            with open(path_config_file, 'r+', encoding='utf-8') as h:
                content = h.read()
                if Path(content) == directory:
                    return

        with open(path_config_file, 'w', encoding='utf-8') as h:
            h.write(str(directory))
    except PermissionError:
        logger.error("Permission Error. Unable to save path to disk.")

def setup_parser() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Neuro Karaoke Archive metadata synchronizer.") 
    parser.add_argument("--path", type=str, default='', help="Path to Archive")
    parser.add_argument("--zipfile", type=str, default='', help="Path to Local Zip File, fetches latest from github if ommitted")
    parser.add_argument("--verbose", action='store_true', help="enable extra debugging log output")

    return parser.parse_args()

def get_raw(json: str, key: str) -> str:

    pattern = f"\"{key}\":\"(.*?)\""

    match = re.search(pattern, json)

    if match is None:
        return ""
    else:
        return match.group(1)
 
@dataclass
class Hjson_Struct:
    metadata: dict[str, str | int | float]
    seen: bool

class Song_Struct:

    raw_payload: str 
    xxhash: str | None
    new_song_data: dict[str, str]
    copy: bool = False
    new_payload: str
    song_obj: Song

    def __init__(self, path: Path | str) -> None:
        self.file_path = Path(path)
        self.song_obj = Song(path)

    def generate_new_path(self) -> Path:
        if self.song_obj.filename != self.file_path.stem:

            renamed_path = self.file_path.parent / self.song_obj.filename
            rename_counter = 1
            base_name = Path(self.song_obj.filename).stem

            while renamed_path.is_file():
                renamed_path = self.file_path.parent / f"{base_name} ({rename_counter}){self.file_path.suffix}"
                rename_counter += 1

            return renamed_path
            
        return self.file_path
        

def main(script_dir: Path) -> None: 

    logger.info("Run start")

    args = setup_parser()

    if args.zipfile and (arg_zipfile := Path(args.zipfile)).is_file() and str(arg_zipfile).endswith(".zip"):
        logger.info("using local zipfile")
        with open(arg_zipfile, 'rb') as file_data:
            bytes_content = file_data.read()
        zip_data = io.BytesIO(bytes_content)
    else:
        logger.info("fetching remote zipfile")
        zip_data = get_remote_zip()

    if zip_data is None:
        logger.critical("Failed to retrieve zip data.")
        exit()        

    with zipfile.ZipFile(zip_data) as zip_ref:
        zipped_files = zip_ref.namelist()

        lookup_table = {metadata["xxHash"] : Hjson_Struct(metadata=metadata, seen=False)
                        for file_path in zipped_files
                        if file_path.endswith('.hjson')
                        and (metadata := get_metadata_from_zip(zip_ref, file_path))}

    path_config_file = script_dir / "path_config.txt"

    preset = setup_preset(script_dir)

    songs_directory_path = get_songs_directory(path_config_file, args)

    if songs_directory_path is None:
        logger.critical("Unable to retrieve path information, ending program")
        exit()

    save_path(path_config_file, songs_directory_path)

    song_files = get_all_mp3(songs_directory_path)
    song_amount = len(song_files)

    if song_amount > 0:
        logger.info(f"Songs Found: {song_amount}")
    else:
        logger.critical("No song files found, please verify path")
        exit()

    start_processing = perf_counter()

    changed = 0

    song_structs = ((i, Song_Struct(song_path)) for i, song_path in enumerate(song_files))

    song_update_threashold = int(song_amount / 100) if song_amount > 100 else 1
    update_indexes = set(n for n in range(song_amount, song_update_threashold))

    for i, song in song_structs:
        if args.verbose:
            logger.info(str(i+1) + '/' + str(song_amount) + ': ' + str(song.file_path)) # TODO log both old and new file name

        song.raw_payload = get_raw_json(song.file_path)
        
        # song.xxhash = get_raw(song.raw_payload, "xxHash")
        song.xxhash = None

        if not song.xxhash:
            song.xxhash = get_audio_hash(song.file_path) # This takes a looooog time

        if song.xxhash is None:
            continue
            
        hjson_data_struct = lookup_table.get(song.xxhash)

        if hjson_data_struct is None:
            continue

        else:
            hjson_data_struct.seen = True

        song.new_song_data = {k : v if isinstance(v, str) else f"{v}" for k, v in hjson_data_struct.metadata.items()}

        for key, value in song.new_song_data.items():
            if get_raw(song.raw_payload, key) != value:
                song.copy = True
                changed += 1
                break

        if not song.copy:
            continue

        song.new_payload = create_payload_from_dict(
                        hjson_data=hjson_data_struct.metadata, 
                        song_path=str(song.file_path), 
                        filename=song.file_path.stem
                        )


        engrave_payload(path=str(song.file_path), song_data=song.new_payload)

        process_new_tags(song.song_obj, song_data=song.new_song_data)

        format_tags(str(song.file_path), script_dir, song.song_obj, preset)

        new_path = song.generate_new_path()
        if " (1)" in str(new_path):
            new_path = Path(str(song.file_path).replace(" (1)", ""))
        os.rename(song.file_path, new_path)


        if i in update_indexes:
            print(f"Files processed: {i+1}/{song_amount}", end='\r', flush=True)
            
    print(f"Files processed: {song_amount}/{song_amount}")

    logger.info("Run Ended")

    logger.info(f"Time to process all files: {round(perf_counter()-start_processing, 2)} seconds")

    seen_hjson_count = sum(1 for hjson_struct in lookup_table.values() if hjson_struct.seen is True) 

    if changed == 0:
        logger.info("No song was changed")
    else:
        logger.info(f"{changed} songs were updated")

    if seen_hjson_count < (len(lookup_table) - 150):
        logger.info("Many files are missing. If this is intentional, feel free to ignore this message.")
        for hjson_struct in lookup_table.values():
            if hjson_struct.seen is False:
                logger.debug(f"Missing {hjson_struct.metadata.get("Track", "")} {hjson_struct.metadata.get("Title", "")}")

    elif all((struct.seen for struct in lookup_table.values())):
        logger.info("Your archive is fully up to date!")

    else:
        logger.info("Some files are missing, check the log file for details.")
        for hjson_struct in lookup_table.values():
            if hjson_struct.seen is False:
                logger.debug(f"Missing {hjson_struct.metadata.get("Track", "")} {hjson_struct.metadata.get("Title", "")}")

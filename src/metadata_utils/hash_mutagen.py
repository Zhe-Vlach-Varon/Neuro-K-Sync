
import mmap
import os

import xxhash
from mutagen.id3 import ID3, ID3NoHeaderError
import logging

logger = logging.getLogger(__name__)

def get_audio_hash(file_path: Path) -> (str | None):
    try:

        file_size = file_path.stat().st_size
        if file_size < 3000:
            print(f"{file_path.name} is too small!")
            return None

        with open(file_path, 'rb') as f:
            file_data = f.read()

            footer_size = 0
            f.seek(-128, 2) # Seek 128 bytes from the end (2)
            if f.read(3) == b'TAG':
                footer_size = 128
            

            if (file_size - footer_size - 1_000_000) > 987: # check to prevent negative indexes
                end_index = file_size - footer_size - 1_000_000 ### about a Mb offset for the audio

            else:
                end_index = int((file_size - footer_size)/2)

            logger.info(f"{file_path} End Index: {end_index}")

            start_index = end_index - 987 ### reads a 987 bytes for the hash

            raw_audio = file_data[start_index:end_index]

        # 4. Hash the raw audio
        hash = xxhash.xxh64(raw_audio).hexdigest()
        logger.info(logger.info(f"{file_path} End Index: {end_index} Hash: {hash}"))
        return hash

    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return None

def get_audio_hash_optimized(file_path: str, chunk_size: int = 65536) -> (str | None):
    try:
        # 1. Calculate boundaries without reading data
        try:
            audio_tags = ID3(file_path)
            header_size = audio_tags.size
        except ID3NoHeaderError:
            header_size = 0

        file_size = os.path.getsize(file_path)
        
        # Check for ID3v1 footer (128 bytes at end)
        footer_size = 0
        with open(file_path, 'rb') as f:
            if file_size > 128:
                f.seek(-128, os.SEEK_END)
                if f.read(3) == b'TAG':
                    footer_size = 128

            # 2. Stream the audio data to the hasher
            hasher = xxhash.xxh64()
            f.seek(header_size)
            
            # Calculate how many bytes we actually need to hash
            remaining_bytes = file_size - header_size - footer_size
            
            while remaining_bytes > 0:
                # Read either the chunk size or what's left
                to_read = min(chunk_size, remaining_bytes)
                data = f.read(to_read)
                if not data:
                    break
                hasher.update(data)
                remaining_bytes -= len(data)

        return hasher.hexdigest()

    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return None


def get_audio_hash_fast(file_path: str) -> (str | None):
    try:
        # 1. Get header size without reading the whole file
        try:
            audio_tags = ID3(file_path)
            header_size = audio_tags.size
        except ID3NoHeaderError:
            header_size = 0

        file_size = os.path.getsize(file_path)
        
        with open(file_path, 'rb') as f:
            # 2. Check for ID3v1 footer (last 128 bytes) without reading whole file
            footer_size = 0
            if file_size > 128:
                f.seek(-128, os.SEEK_END)
                if f.read(3) == b'TAG':
                    footer_size = 128
            
            # 3. Use memory mapping for the "raw" audio portion
            # This is significantly faster for large files
            if file_size - header_size - footer_size <= 0:
                return None

            with mmap.mmap(f.fileno(), length=0, access=mmap.ACCESS_READ) as mm:
                # Slice the mmap (this is a memory view, not a copy)
                raw_audio_view = mm[header_size : file_size - footer_size]
                return xxhash.xxh64(raw_audio_view).hexdigest()

    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return None

def get_audio_hash_short(file_path: str) -> (str | None):
    try:
        with open(file_path, 'rb') as f:
            file_data = f.read()

        footer_size = 128 if file_data[-128:].startswith(b'TAG') else 0
        
        end_index = len(file_data) - footer_size
        raw_audio = file_data[end_index-500:end_index]

        return xxhash.xxh64(raw_audio).hexdigest()

    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return None

def get_audio_hash_short_fast(file_path: str) -> (str | None):
    try:
        file_size = os.path.getsize(file_path)
        footer_size = 0
        with open(file_path, 'rb') as f:
            if file_size > 128:
                f.seek(-128, os.SEEK_END)
                if f.read(3) == b'TAG':
                    footer_size = 128

            f.seek(-1000, os.SEEK_END-footer_size)
            data = f.read(1000)

        return xxhash.xxh64(data).hexdigest()

    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return None


import mmap
import os

import xxhash
from mutagen.id3 import ID3, ID3NoHeaderError
import logging

logger = logging.getLogger(__name__)

def get_audio_hash(file_path: Path) -> (str | None):
    try:

        try:
            audio_tags = ID3(file_path)
            header_size = audio_tags.size  # Mutagen provides the full tag size including header
        except ID3NoHeaderError:
            header_size = 0

        print(file_path.stat().st_size)
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
                end_index = int((file_size - footer_size - header_size) * 3 / 4 + header_size)

            print(f"End Index: {end_index}")

            start_index = end_index - 987 ### reads a 987 bytes for the hash

            raw_audio = file_data[start_index:end_index]

        # 4. Hash the raw audio
        return xxhash.xxh64(raw_audio).hexdigest()

    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return None
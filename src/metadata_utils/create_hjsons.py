import os

from .data_verification import validate_payload
from .engraver import build_payload


def create_payload_from_dict(hjson_data: dict[str, (str | int | float)], song_path: str, filename: (str | None) = None) -> str:
    ARG_MAP = {
        "Date": "date",
        "Title": "title",
        "TitleOG": "title_og",
        "Identify": "identify",
        "Artist": "artist",
        "ArtistOG": "artist_og",
        "CoverArtist": "cover_artist",
        "Version": "version",
        "Discnumber": "disc_number",
        "Track": "track",
        "Comment": "comment",
        "Special": "special",
        "xxHash": "xxhash"
    }

    if "Comment" not in hjson_data.keys():
        hjson_data["Comment"] = "None"

    if "TitleOG" not in hjson_data.keys():
        hjson_data["TitleOG"] = "None"

    if "Identify" not in hjson_data.keys():
        hjson_data["Identify"] = "None"

    if "ArtistOG" not in hjson_data.keys():
        hjson_data["ArtistOG"] = "None"

    if "Special" not in hjson_data.keys():
        hjson_data["Special"] = "0"

    payload_kwargs = {
    ARG_MAP[field]: str(hjson_data[field]) for field in ARG_MAP
    }


    payload_kwargs["filename"] = filename if filename else os.path.basename(song_path)

    validate_payload(payload_kwargs)
    
    return build_payload(**payload_kwargs)

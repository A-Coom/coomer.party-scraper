import hashlib
import logging
import os
import re
from pathlib import Path
from sys import maxsize
from typing import Optional, Set, Tuple


logger = logging.getLogger(__name__)


"""
Get the base URL of a given URL (naive, not very robust)
- url: URL to parse
Returns the second and top level domain of the URL
"""
def base_url(url: str) -> str:
    match = re.match(r'^https://[^/]+\.[^/]+', url)
    if match is not None:
        base = match.group(0)
    else:
        base = ''
    logger.debug(f'Base URL of ({url}) --> ({base})')
    return base


"""
Compute the hash of all files in a directory, including subdirectories.
This is the hash that is used in the media URLs.
- root: Starting path to hash from.
Returns a set of unique hashes from root.
"""
def compute_file_hashes(root: Path) -> Set[str]:
    hashes = set()
    if not root.exists():
        logger.debug(f'compute_file_hashes: root does not exist: {root}')
        return hashes

    for file in root.glob('**/*'):
        if file.is_dir() or file.suffix == '.part':
            logger.debug(f'Skipping file: {file} (dir or .part)')
            continue

        # Verbose: announce which file we're hashing right now
        logger.debug(f'Hashing file: {file}')

        with file.open('rb') as f:
            curr_hash = hashlib.sha256()
            while True:
                chunk = f.read(10 * 1024)
                if not chunk:
                    break
                curr_hash.update(chunk)
            file_hash = curr_hash.hexdigest()
            hashes.add(file_hash)

        # Verbose: show computed hash for the file
        logger.debug(f'Computed hash {file_hash} for {file}')
    return hashes


"""
Create the folder structure for download destinations
- dst: Root destination for all downloads
- user: Subfolder in the root, usually based on the username
- skip_img: If images are being skipped for downloads
- skip_vid: If videos are being skipped for downloads
"""
def create_folder_tree(dst: Path, user: str, skip_img: bool, skip_vid: bool) -> None:
    dst_pics = dst / user / 'pics'
    dst_vids = dst / user / 'vids'
    try:
        if not skip_img:
            os.makedirs(dst_pics)
    except FileExistsError:
        pass
    try:
        if not skip_vid:
            os.makedirs(dst_vids)
    except FileExistsError:
        pass
    return


"""
Round offsets in an API-friendly that includes the intended range.
- offsets: Offsets to round.
- modulo: Unit to round down or up by.
Returns the offsets rounded to the nearest number that is divisble by the modulo.
"""
def round_offsets( offsets: Tuple[Optional[int], Optional[int]]
                 , modulo: int) -> Tuple[int, int]:
    rounded_start = 0
    if offsets[0] is not None and offsets[0] % modulo != 0:
        rounded_start = offsets[0] - (offsets[0] % modulo)
    rounded_end = maxsize
    if offsets[1] is not None:
        rounded_end = offsets[1] - (offsets[1] % modulo) + modulo
        if offsets[1] % modulo == 0:
            rounded_end -= modulo
    if rounded_start != 0 or rounded_end != maxsize:
        rounded_start_str = '0' if offsets[0] is None else str(rounded_start)
        rounded_end_str = 'inf' if offsets[1] is None else str(rounded_end)
        start_str = '0' if offsets[0] is None else str(offsets[0])
        end_str = 'inf' if offsets[1] is None else str(offsets[1])
        logger.info(f'Fetching posts in clamped range [{rounded_start_str}, {rounded_end_str}].')
        logger.info(f'This will be pruned to [{start_str}, {end_str}] before downloading.')
    return (rounded_start, rounded_end)


"""
Sanitize the beginning of a URL to include https://www.
- url: URL to sanitize.
Returns the sanitized URL.
"""
def sanitize_url(url: str) -> str:
    sanitized = re.sub(r'^https?://', '', url)
    sanitized = re.sub(r'^www\.', '', sanitized)
    sanitized = 'https://' + sanitized
    if sanitized[-1] == '/':
        sanitized = sanitized[:-1]
    logger.debug(f'Santized URL ({url}) --> ({sanitized})')
    return sanitized


"""
Convert a sentence to CamelCase.
- sentence: Sentence to convert.
Returns the camel case equivalent.
"""
def to_camel(sentence: str) -> str:
    return ''.join([ word.capitalize() for word in sentence.split() ])
import logging
import queue
import requests
import time

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from random import randrange
from tqdm import tqdm
from typing import List, Optional


IMG_EXTS = [ 'jpg', 'jpeg', 'png', 'gif', 'webp' ]
VID_EXTS = [ 'mp4', 'm4v', 'mkv', 'mov', 'wmv', 'webm', 'avi', 'flv', 'mp3' ]

THROTTLE_TIME = 30
CHUNK_SIZE = 10 * 1024

logger = logging.getLogger(__name__)


"""
Wrapper class to associate a URL with a name
"""
@dataclass
class NamedUrl:
    url: str
    name: str


"""
Wrapper class to describe download progress
"""
@dataclass
class _ProgressUpdate:
    slot: int
    done: int
    total: Optional[int]
    desc: str
    n: int
    finished: bool = False
    paused: bool = False


"""
Download a single URL, cycling through random load-balancing servers.
- url: NamedUrl to download.
- dst: Destination of the URL.
- slot: Position in the progress rendering
- q: The queue that this job belongs to
"""
def _download( url: NamedUrl, dst: Path, slot: int, q: queue.Queue ) -> None:
    server_ident = randrange(4) + 1
    static_url = url.url[10:]
    tmp = dst.with_suffix(dst.suffix + '.part')
    total = None

    while True:
        headers = { 'Connection': 'close' }
        done = tmp.stat().st_size if tmp.exists() else 0
        if done > 0:
            headers['Range'] = f'bytes={done}-'
        
        real_url = f'https://n{server_ident}{static_url}'
        q.put(_ProgressUpdate(slot, done, total, url.name, server_ident))

        try:
            with requests.get(real_url, stream=True, timeout=(3, 3), headers=headers) as res:
                res.raise_for_status()

                if total is None:
                    cl = res.headers.get('Content-Length')
                    cr = res.headers.get('Content-Range')
                    if cr is not None:
                        total = int(cr.split('/')[-1])
                    elif cl is not None:
                        total = int(cl)

                with tmp.open('ab') as f:
                    for chunk in res.iter_content(chunk_size=CHUNK_SIZE):
                        if not chunk:
                            continue
                        f.write(chunk)
                        done += len(chunk)
                        q.put(_ProgressUpdate(slot, done, total, url.name, server_ident))
                tmp.replace(dst)

        except (requests.RequestException, requests.exceptions.ReadTimeout):
            q.put(_ProgressUpdate(slot, done, total, url.name, server_ident, paused=True))
            time.sleep(THROTTLE_TIME)
            server_ident = randrange(3) + 1
            q.put(_ProgressUpdate(slot, done, total, url.name, server_ident))

        else:
            q.put(_ProgressUpdate(slot, done, total, url.name, server_ident, finished=True))
            return


"""
Use the Coomer/Kemono API to fetch a collection of posts.
- base: Base URL for the API (includes up the the TLD).
- service: Service the media originates from.
- creator: Creator of the media.
- offset: Offset into all of the posts to fetch from.
Returns a collection of posts, including possibly an empty collection
"""
def api_fetch_post_multi(base: str, service: str, creator: str, offset: int) -> List[dict]:
    api_url = f'{base}/api/v1/{service}/user/{creator}/posts?o={offset}'
    while True:
        try:
            res = requests.get(api_url, headers={'accept': 'text/css'})
        except Exception:
            if res.status_code in [429, 403]:
                time.sleep(THROTTLE_TIME)
        else:
            break

    if res.status_code != 200:
        logger.error(f'Failed to fetch posts using the API ({api_url}) --> {res.status_code}')
        return []

    return res.json()


"""
Use the Coomer/Kemono API to fetch a single post.
- base: Base URL for the API (includes up the the TLD).
- service: Service the media originates from.
- creator: Creator of the media.
- post_id: Post ID to query.
Returns a single post.
"""
def api_fetch_post_single(base: str, service: str, creator: str, post_id: str) -> dict:
    api_url = f'{base}/api/v1/{service}/user/{creator}/post/{post_id}'
    while True:
        try:
            res = requests.get(api_url, headers={'accept': 'text/css'})
        except Exception:
            if res.status_code in [429, 403]:
                time.sleep(THROTTLE_TIME)
        else:
            break

    if res.status_code != 200:
        logger.error(f'Failed to fetch posts using the API ({api_url}) --> {res.status_code}')
        return {}

    return res.json()


"""
Download a list of NamedUrl using multithreading, checking for duplicates.
- urls: List of NamedUrl to download.
- dst_pics: Path to download pictures to.
- dst_vids: Path to download videos to.
- workers: Maximum number of threads to use for downloading.
Returns the number of unique downloads successfully performed.
"""
def multithread_download( urls: List[NamedUrl]
                        , dst_pics: Path
                        , dst_vids: Path
                        , hashes: dict[bytes, Path] = {}
                        , workers: int = 8
                        ) -> dict[bytes, Path]:
    q: queue.Queue = queue.Queue()
    url_iter = iter(urls)
    max_desc_width = max((len(u.name) for u in urls), default=0) + 6

    with ThreadPoolExecutor(max_workers=workers) as pool:
        # Create a "master" bar the denotes total progress
        master_bar = tqdm(total=len(urls), unit="file", desc="Total Media Files", position=0)

        # Initialize tqdm bars for the fixed number of workers
        bars: List[tqdm] = [tqdm(unit="B", unit_scale=True, unit_divisor=1024, position=i+1) for i in range(workers)]

        # Helper to submit the next available URL to a specific slot
        def submit_next(slot: int) -> bool:
            try:
                next_url = next(url_iter)
                dst = (dst_pics if next_url.url.split('.')[-1] in IMG_EXTS else dst_vids) / next_url.name
                pool.submit(_download, next_url, dst, slot, q)
                return True
            except StopIteration:
                return False

        # Initialize necessary slots
        active_workers = 0
        for slot in range(workers):
            if submit_next(slot):
                active_workers += 1
            else:
                bars[slot].clear()

        # Continually refill slots as jobs finish
        while active_workers > 0:
            try:
                msg = q.get(timeout=0.1)
            except queue.Empty:
                continue

            bar = bars[msg.slot]
            if msg.paused:
                bar.set_description((f'[ {msg.n}*] ' + msg.desc).ljust(max_desc_width))
            else:
                bar.set_description((f'[ {msg.n} ] ' + msg.desc).ljust(max_desc_width))

            if msg.finished:
                master_bar.update(1)
                if submit_next(msg.slot):
                    bar.reset()
                else:
                    active_workers -= 1
            else:
                if msg.total:
                    bar.total = msg.total
                bar.n = msg.done
                bar.refresh()

    return hashes
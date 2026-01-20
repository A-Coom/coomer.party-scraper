import logging
import re
from pathlib import Path
from sys import maxsize
from typing import List, Optional, Tuple

from .networking import ( api_fetch_post_multi, api_fetch_post_single
                        , multithread_download, NamedUrl, IMG_EXTS, VID_EXTS )
from .utils import base_url, compute_file_hashes, create_folder_tree, round_offsets, to_camel


POSTS_PER_FETCH = 50

logger = logging.getLogger(__name__)


"""
Extract media URLs from a list of post JSONs
- base: Base URL that the media should be one
- posts: List of post JSONs to parse
- skip_img: If images should be skipped
- skip_vid: if videos should be skipped
Returns a list of NamedUrl extracted from the posts
"""
def parse_posts_json( base: str
                    , posts: List[dict]
                    , skip_img: bool
                    , skip_vid: bool ) -> List[NamedUrl]:
    named_urls = []
    base = base.replace('https://', 'https://n1.')
    for post in posts:
        title = to_camel(re.sub(r'[^A-Za-z0-9\s]+', '', post['title']))
        datetime = re.sub('-|:', '', post['published'])
        if 'path' in post['file']:
            ext = post['file']['path'].split('.')[-1]
            if skip_vid and ext in VID_EXTS:
                continue
            if skip_img and ext in IMG_EXTS:
                continue
            name = f'{datetime}-{title}_0.{ext}'
            url = f'{base}/data/{post["file"]["path"]}'
            named_urls.append(NamedUrl(url, name))

        for i, attachment in enumerate(post['attachments']):
            ext = attachment['path'].split('.')[-1]
            if skip_vid and ext in VID_EXTS:
                continue
            if skip_img and ext in IMG_EXTS:
                continue
            url = f'{base}/data/{attachment["path"]}'
            name = f'{datetime}-{title}_{i+1}.{ext}'
            named_urls.append(NamedUrl(url, name))
    return named_urls



"""
Process a pre-fetched media URL
- url: Main URL of the pre-fetched media
- skip_img: If image downloads should be skipped.
- skip_vid: If video downloads should be skipped.
Returns a single-element list of NamedUrl for the pre-fetched media.
"""
def process_prefetched( url: str
                      , skip_img: bool
                      , skip_vid: bool ) -> List[NamedUrl]:
    # Further sanitize the URL
    url = url.split('?')[0]

    # Use the hash as the name
    name = url.split('/')[-1]

    # Ensure it shouldn't be skipped (for some reason)
    ext = name.split('.')[-1]
    if (ext in IMG_EXTS and skip_img) or (ext in VID_EXTS and skip_vid):
        return []

    # Create the NamedUrl
    named_urls = [ NamedUrl(url, name) ]
    return named_urls


"""
Process a post to get all media URLs
- url: Main URL of the post.
- skip_img: If image downloads should be skipped.
- skip_vid: If video downloads should be skipped.
Returns a list of NamedUrl extracted from the post.
"""
def process_post( url: str
                , skip_img: bool
                , skip_vid: bool ) -> List[NamedUrl]:
    # Get the SLD and TLD of the URL
    base = base_url(url)
    segments = url.split('/')
    service = segments[-5]
    creator = segments[-3]
    post_id = segments[-1]

    # Get the JSON version of the post
    post = [ api_fetch_post_single(base, service, creator, post_id)['post'] ]

    # Parse the media URLs from the post
    logger.info('Parsing media URLs from 1 post')
    named_urls = parse_posts_json(base, post, skip_img, skip_vid)
    logger.info(f'Found {len(named_urls)} media files to download')

    # Remove duplicates by finding multiple posts that show the same media
    # I imagine this can only happen by mistake of the uploader
    seen = set()
    unique_urls = []
    for nu in named_urls:
        if nu.url not in seen:
            seen.add(nu.url)
            unique_urls.append(nu)
    return unique_urls


"""
Process a page to get all media URLs.
- url: Main URL of the page.
- skip_img: If image downloads should be skipped.
- skip_vid: If video downloads should be skipped.
- offsets: Range of offsets to download.
Returns a list of NamedUrl extracted from all posts belonging to the page.
"""
def process_page( url: str
                , skip_img: bool
                , skip_vid: bool
                , offsets: Tuple[Optional[int], Optional[int]] ) -> List[NamedUrl]:
    # Get the SLD and TLD of the URL
    base = base_url(url)
    segments = url.split('/')
    service = segments[-3]
    creator = segments[-1]

    # Round the offsets
    rounded_offsets = round_offsets(offsets, POSTS_PER_FETCH)

    # Iterate through post ranges for the page
    all_posts = []
    offset = rounded_offsets[0]
    while True:
        logger.info(f'Fetching posts {offset + 1} - {offset + POSTS_PER_FETCH}')
        curr_posts = api_fetch_post_multi(base, service, creator, offset)
        all_posts += curr_posts
        offset += POSTS_PER_FETCH
        if len(curr_posts) % POSTS_PER_FETCH != 0 or len(curr_posts) == 0 or offset >= rounded_offsets[1]:
            break
    
    # Prune to user-requested offsets
    if rounded_offsets[0] != 0 and offsets[0] is not None:
        skip_start = offsets[0] - rounded_offsets[0] - 1
        all_posts = all_posts[skip_start:]
    if rounded_offsets[1] != maxsize and offsets[1] is not None:
        skip_end = rounded_offsets[1] - offsets[1]
        all_posts = all_posts[:-skip_end]

    # Parse the media URLs from each post
    logger.info(f'Parsing media URLs from {len(all_posts)} posts')
    named_urls = parse_posts_json(base, all_posts, skip_img, skip_vid)
    logger.info(f'Found {len(named_urls)} media files to download')

    # Remove duplicates by finding multiple posts that show the same media
    seen = set()
    unique_urls = []
    for nu in named_urls:
        if nu.url not in seen:
            seen.add(nu.url)
            unique_urls.append(nu)
    return unique_urls


"""
Remove duplicate URLs based on the SHA-256 hash of existing files.
Note that since URLs are hashes, there should be no duplicates between posts.
- dst: Directory to check for existing files.
- named_urls: URLs to remove duplicates from.
Returns a possibily reduced list of URLs
"""
def purge_duplicate_urls(dst: Path, named_urls: List[NamedUrl]) -> List[NamedUrl]:
    # Get the hashes of the existing files
    hashes = compute_file_hashes(dst)

    # Remove duplicates by finding URLs that includ the hash
    unique_urls = []
    for nu in named_urls:
        url_hash = nu.url.split('/')[-1].split('.')[0]
        if url_hash not in hashes:
            unique_urls.append(nu)
        else:
            logger.debug(f'Removing from download list based on hash: {url_hash}')
    return unique_urls


"""
Driver function to download media from Coomer or Kemono
- urls: List of URLs to download from (page, post, or pre-fetched media)
- dst: Download destination for the media (per-creator subfolders will be made)
- skip_img: If image files should be skipped when downloading
- skip_vid: If video files should be skipped whne downloading
- offsets: Post offsets to start from and end at when downloading a page.
- dump_urls: If URLs should be dumped instead of downloaded from.
- jobs: Maximum number of threads to perform downloads, one thread per download.
"""
def main( urls: List[str]
        , dst: Path
        , skip_img: bool
        , skip_vid: bool
        , offsets: Tuple[Optional[int], Optional[int]]
        , dump_urls: bool
        , jobs: int) -> None:

    # Loop through the URLs to get more URLs
    for url in urls:
        logger.info(f'Parsing argument-provided URL "{url}"')

        # Split the URL on the separator
        segments = url.split('/')
        if len(segments) < 4:
            logger.error('The URL is malformed')
            return
        user = None

        # Fetch URLs to download media from a post
        if segments[-2] == 'post':
            logger.debug('URL is suspected to be a post')
            if offsets[0] is not None or offsets[1] is not None:
                logger.warning('Start and end offsets are ignored when downloading a post')
            user = segments[-3]
            named_urls = process_post(url, skip_img, skip_vid)

        # Fetch URLs to download media from pre-fetched media
        elif segments[-4] == 'data':
            logger.debug('URL is suspected to be pre-fetched media')
            if offsets[0] is not None or offsets[1] is not None:
                logger.warning('Start and end offsets are ignored when downloading pre-fetched media')
            logger.warning('Cannot determine username for pre-fetched media. Download will be in a folder named "unknown"')
            user = 'unknown'
            named_urls = process_prefetched(url, skip_img, skip_vid)

        # Fetch URLs to download media from a page
        else:
            logger.debug('URL is suspected to be a page')
            user = segments[-1]
            named_urls = process_page(url, skip_img, skip_vid, offsets)

        # Remove URLs of files that already exist
        dst_root = dst / user
        logger.info(f'Begin hashing files in {dst_root}')
        named_urls = purge_duplicate_urls(dst_root, named_urls)
        logger.info(f'New number of media files to download is {len(named_urls)}')

        # Conditionally dump the URLs and return
        if dump_urls:
            for nu in named_urls:
                print(f'{nu.name}\t{nu.url}') # Print is used here instead of logging for a better UX
            return

        # Create the folder tree for the download destination
        create_folder_tree(dst, user, skip_img, skip_vid)

        # Perform the downloads
        dst_pics = dst_root / 'pics'
        dst_vids = dst_root / 'vids'
        logger.info(f'Downloading to {dst / user}')
        multithread_download(named_urls, dst_pics, dst_vids, workers=jobs)

    return
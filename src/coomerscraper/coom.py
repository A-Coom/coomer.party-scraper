import logging
import re
from pathlib import Path
from sys import maxsize
from typing import List, Optional, Tuple

from .networking import ( api_fetch_post_multi, api_fetch_post_single
                        , multithread_download, NamedUrl, IMG_EXTS, VID_EXTS )
from .utils import base_url, compute_file_hashes, create_folder_tree, round_offsets, to_camel

from .rate_limiter import RateLimiter
from .template import TemplateManager, PathTemplate

POSTS_PER_FETCH = 50

logger = logging.getLogger(__name__)


"""
Extract media URLs from a list of post JSONs
- base: Base URL that the media should be one
- posts: List of post JSONs to parse
- skip_img: If images should be skipped
- skip_vid: if videos should be skipped
- service: Service name
- creator: Creator username
- template_manager: Template manager for custom paths 
- use_template: If templates should be used for naming
Returns a list of NamedUrl extracted from the posts
"""
def parse_posts_json( base: str
                    , posts: List[dict]
                    , skip_img: bool
                    , skip_vid: bool
                    , service: str = ''
                    , creator: str = ''
                    , template_manager: Optional[TemplateManager] = None
                    , use_template: bool = False) -> List[NamedUrl]:
    named_urls = []
    base = base.replace('https://', 'https://n1.')

    for idx, post in enumerate(posts):
        raw_title = post.get('title', '') or ''
        title = re.sub(r'[^A-Za-z0-9\s\-_]', '_', raw_title)
        title = re.sub(r'_+', '_', title)
        title = re.sub(r'\s+', ' ', title).strip() #maybe allow emojis later
        if not title:
            title = post.get('id', '')

        datetime = re.sub('[-:]', '', post['published'])
        post_id = post.get('id', post['id'])

        if 'path' in post['file']:
            ext = post['file']['path'].split('.')[-1]
            if skip_vid and ext in VID_EXTS:
                continue
            elif skip_img and ext in IMG_EXTS:
                continue
            else:
                url = f'{base}/data/{post["file"]["path"]}'
                if use_template and template_manager:
                    basename = post['file']['name']
                    filename = basename.split('.', 1)[0]
                    m = re.search(r'([0-9a-f]{16,64})', filename)
                    file_hash = m.group(1) if m else filename

                    context = {
                        'service': service,
                        'creator': creator,
                        'post': title or post_id,
                        'index': 0,
                        'filename': filename,
                        'filehash': file_hash,
                        'extension': f'.{ext}',
                        'date': post['published'].split("T")[0].replace("-", ""),
                        'id': post_id
                    }

                    is_image = ext in IMG_EXTS
                    is_video = ext in VID_EXTS
                    custom_path = template_manager.get_path(context, is_image=is_image, is_video=is_video)
                    name = str(custom_path.relative_to(template_manager.output_dir))
                else:
                    name = f'{datetime}-{title}_0.{ext}'
                named_urls.append(NamedUrl(url, name))

        for i, attachment in enumerate(post['attachments']):
            ext = attachment['path'].split('.')[-1]
            if skip_vid and ext in VID_EXTS:
                continue
            if skip_img and ext in IMG_EXTS:
                continue

            url = f'{base}/data/{attachment["path"]}'
            if use_template and template_manager:
                basename = post['file']['name']
                filename = basename.split('.', 1)[0]
                m = re.search(r'([0-9a-f]{16,64})', filename)
                file_hash = m.group(1) if m else filename

                context = {
                    'service': service,
                    'creator': creator,
                    'post': title or post_id,
                    'index': str(i + 1),
                    'filename': filename,
                    'filehash': file_hash,
                    'extension': f'.{ext}',
                    'date': post['published'].split("T")[0].replace("-", ""),
                    'id': post_id
                }

                is_image = ext in IMG_EXTS
                is_video = ext in VID_EXTS
                custom_path = template_manager.get_path(context, is_image=is_image, is_video=is_video)
                name = str(custom_path.relative_to(template_manager.output_dir))
            else:
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
- rate_limiter: Rate limiter for API requests.
Returns a list of NamedUrl extracted from the post.
"""
def process_post( url: str
                , skip_img: bool
                , skip_vid: bool
                , rate_limiter: Optional[RateLimiter] = None
                , template_manager: Optional[TemplateManager] = None) -> List[NamedUrl]:
    # Get the SLD and TLD of the URL
    base = base_url(url)
    segments = url.split('/')
    service = segments[-5]
    creator = segments[-3]
    post_id = segments[-1]

    if rate_limiter:
        rate_limiter.wait()

    # Get the JSON version of the post
    post = [ api_fetch_post_single(base, service, creator, post_id)['post'] ]

    # Parse the media URLs from the post
    logger.info('Parsing media URLs from 1 post')

    use_template = template_manager is not None
    named_urls = parse_posts_json(base, post, skip_img, skip_vid, service, creator, template_manager, use_template)

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
- rate_limiter: Rate limiter for API requests.
- template_manager: Template manager for custom paths
Returns a list of NamedUrl extracted from all posts belonging to the page.
"""
def process_page( url: str
                , skip_img: bool
                , skip_vid: bool
                , offsets: Tuple[Optional[int], Optional[int]]
                , rate_limiter: Optional[RateLimiter] = None
                , template_manager: Optional[TemplateManager] = None) -> List[NamedUrl]:
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

        if rate_limiter:
            rate_limiter.wait()

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

    use_template = template_manager is not None
    named_urls = parse_posts_json(base, all_posts, skip_img, skip_vid, service, creator, template_manager, use_template)

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
Returns a possibly reduced list of URLs
"""
def purge_duplicate_urls(dst: Path, named_urls: List[NamedUrl]) -> List[NamedUrl]:
    # when using templates like "[<t:service>]<t:creator>/..." files are grouped in folders
    # detailed file listing is unnecessary for folders we aren't writing to
    scan_roots = set()
    found_structure = False

    for nu in named_urls:
        # check if the name implies a directory structure
        parts = Path(nu.name).parts
        if len(parts) > 1:
            found_structure = True
            # add the top-level folder of this file to the scan list
            scan_roots.add(dst / parts[0])

    hashes = set()
    if found_structure and scan_roots:
        logger.info(f'Template structure detected. Limiting existing file scan to {len(scan_roots)} related folder(s): {[p.name for p in scan_roots]}')
        for root in scan_roots:
            hashes.update(compute_file_hashes(root))
    else:
        # fallback scan the entire destination directory
        logger.info(f'Scanning all files in {dst} for existing hashes')
        hashes = compute_file_hashes(dst)

    # remove duplicates by finding URLs that include the hash
    unique_urls = []
    for nu in named_urls:
        # strip query parameters and get the filename from the URL
        url_filename = nu.url.split('?')[0].rstrip('/').split('/')[-1]
        m = re.search(r'([0-9a-f]{16,64})', url_filename)
        url_hash = m.group(1) if m else None

        # if not in url, try to find a hash in the (possibly template-based) name
        if url_hash is None:
            m2 = re.search(r'([0-9a-f]{16,64})', nu.name)
            url_hash = m2.group(1) if m2 else None

        if url_hash:
            if url_hash in hashes:
                logger.debug(f'Removing from download list based on hash: {url_hash}')
                continue
            else:
                unique_urls.append(nu)
                continue

        # no hash found -> go back to checking if the dest file already exists
        candidate = dst / nu.name
        if candidate.exists():
            logger.debug(f'Removing from download list because file exists: {candidate}')
            continue

        unique_urls.append(nu)
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
- rate_limit:  Rate limit in requests per second
- template: Custom path template for downloads
- image_template: Custom path template for image downloads
- video_template: Custom path template for video downloads
"""
def main( urls: List[str]
        , dst: Path
        , skip_img: bool
        , skip_vid: bool
        , offsets: Tuple[Optional[int], Optional[int]]
        , dump_urls: bool
        , jobs: int
        , rate_limit: int = 2
        , template: Optional[str] = None
        , image_template: Optional[str] = None
        , video_template: Optional[str] = None) -> None:
    template_manager = None
    if template:
        template_manager = TemplateManager(dst, template, image_template, video_template)
        logger.info(f'Using template {template}')
        if image_template:
            logger.info(f'Using image template {image_template}')
        if video_template:
            logger.info(f'Using video template {video_template}')

    rate_limiter = RateLimiter(rate_limit)
    logger.info(f'Rate limit set to {rate_limit} requests/s')

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
            named_urls = process_post(url, skip_img, skip_vid, rate_limiter, template_manager)

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
            named_urls = process_page(url, skip_img, skip_vid, offsets, rate_limiter, template_manager)

        # When using templates the destination is already in the path
        if template_manager:
            dst_root = dst
            logger.info(f'Begin hashing files in {dst_root}')
            named_urls = purge_duplicate_urls(dst_root, named_urls)
        else:
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

        if template_manager:
            # create folder based on template
            dst.mkdir(exist_ok=True, parents=True)
            dst_pics = dst
            dst_vids = dst
        else:
            # Create the folder tree for the download destination
            create_folder_tree(dst, user, skip_img, skip_vid)
            dst_pics = dst_root / 'pics'
            dst_vids = dst_root / 'vids'

        logger.info(f'Downloading to {dst / user if not template_manager else dst}')
        multithread_download(named_urls, dst_pics, dst_vids, workers=jobs, rate_limiter=rate_limiter, use_template=template_manager is not None)

    return
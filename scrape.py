from scraping_utils.scraping_utils import compute_file_hashes, DownloadThread, multithread_download_urls_special, IMG_EXTS, VID_EXTS, TOO_MANY_REQUESTS, NOT_FOUND, CONNECTION_RESET, THROTTLE_TIME
from sys import stderr, stdout, argv, maxsize
from hashlib import md5, sha256
import argparse
import os
import time
import re
import requests


POSTS_PER_FETCH = 50


"""
A class to download a Coomer URL to a directory on a separate thread.
The alternate coom servers will be swapped when "too many requests" is received as a response
"""
class CoomerThread(DownloadThread):
    # Coom server information
    SERVER_IDENT = 'n'
    C_SERVER_COUNT = 4
    F_TOKEN = 'A-Coom@github'

    # Initialize this CoomerThread
    def __init__(self, file_name, url, dst, algo=md5, hashes={}):
        DownloadThread.__init__(self, file_name, url, dst, algo, hashes)
        self.base = url
        self.server = 1
        self.coomit()

    # Update the coom server URL from the base URL
    def coomit(self):
        ext = self.base.split('.')[-1]
        host = self.base.split('/')[2].split('.')[1]
        name = self.base.split('/')[-1].split('.')[0]
        t1 = name[0:2]
        t2 = name[2:4]
        self.url = f'http://{self.SERVER_IDENT}{self.server}.{host}.su/data/{t1}/{t2}/{name}.{ext}?f={self.F_TOKEN}.{ext}'
        self.server = self.server + 1
        if(self.server > self.C_SERVER_COUNT): self.server = 1

    # Throttle the thread
    def throttle(self):
        self.status = self.STANDBY
        self.coomit()
        if(self.server == 1):
            time.sleep(THROTTLE_TIME)

    # Safely make a streamed connection
    def establish_stream(self, start=-1):
        while(True):
            try:
                headers = { 'Range': f'bytes={start}-' } if start > 0 else {}
                r = requests.get(self.url, headers=headers, stream=True, allow_redirects=True)
                r.raise_for_status()
                
                # Return the streamed connection
                return r
            except:
                self.throttle()
    
    # Perform downloading until successful, switching coom servers as "too many requests" responses are received
    def run(self):
        # Craft the file name and its temporary name
        out_name = os.path.join(self.dst, self.name)
        tmp_name = f'{out_name}.part'

        # Establish the streamed connection
        self.status = self.CONNECTING
        r = self.establish_stream()

        # Get total content size of file
        self.total_size = int(r.headers.get("content-length", 1))
        self.downloaded = 0

        # Track if hashing has occurred
        did_hash = False
        is_duplicate = False

        # Open the temporary file
        chunk_size = 1024 * 1024 * 2
        with open(tmp_name, 'wb') as tmp_file:
            # Download in chunks
            while(True):
                try:
                    # Try to download the chunks
                    self.status = self.DOWNLOADING

                    # Process every chunk
                    for chunk in r.iter_content(chunk_size):    
                        # Ensure hash has not been seen before if using short hash
                        if(not did_hash):
                            if(self.algo == md5):
                                self.status = self.HASHING
                                hash = self.algo(chunk[:1024*64]).hexdigest()
                                if(hash in self.hashes):
                                    is_duplicate = True
                                    break
                                self.hashes[hash] = self.name
                            else:
                                self.hashes[len(self.hashes)] = self.name
                            did_hash = True

                        self.status = self.DOWNLOADING
                        tmp_file.write(chunk)
                        self.downloaded += len(chunk)
                
                except Exception as e:
                    if(r.status_code == NOT_FOUND):
                        self.status = self.ERROR
                        break
                    r.close()
                    r = self.establish_stream(start=self.downloaded)

                # download is successful or duplicate hash was found
                else:
                    break

        # On unrecoverable error, remove temp file
        if(self.status == self.ERROR):
            os.remove(tmp_name)
            return

        # Handle file renaming with consideration to duplicate files
        self.status = self.WRITING
        if(is_duplicate):
            os.remove(tmp_name)
        else:
            try: os.remove(out_name)
            except: pass
            os.rename(tmp_name, out_name)
        self.status = self.FINISHED


"""
Convert a sentence to CamelCase.
@param sentence - Sentence to convert.
@return the camel case equivalent.
"""
def to_camel(sentence):
    words = sentence.split()
    camel = ''.join(word.capitalize() for word in words)
    return camel


"""
Delete empty and .part files from a directory.
@param path - Path to the directory to delete files from
@return None.
"""
def delete_download_artifacts(path):
    if(not os.path.isdir(path)): return
    for f in os.listdir(path):
        f_path = os.path.join(path, f)
        if(os.path.isfile(f_path) and (f_path.endswith('.part') or os.stat(f_path).st_size == 0)):
            os.remove(f_path)
    return


"""
Download media from posts on coomer.su
@param urls - Dictionary of named urls for the media of the creator.
@param include_imgs - Boolean for if to include images.
@param include_vids - Boolean for if to include videos.
@param dst - Destination directory for the downloads.
@param full_hash - Calculate a full hash for quick comparisons.
@return the total number of media entries downloaded this session.
"""
def download_media(urls, include_imgs, include_vids, dst, full_hash):
    # Craft the download paths
    stdout.write('[download_media] INFO: Computing hashes of existing files.\n')
    hashes = {}
    pics_dst = os.path.join(dst, 'Pics');
    vids_dst = os.path.join(dst, 'Vids');

    # Determine the hashing algorithm
    algo = md5
    if(full_hash): algo = sha256

    # Create the image path or compute the hashes of its files
    if(include_imgs):
        if(os.path.isdir(pics_dst)):
            delete_download_artifacts(pics_dst)
            hashes = compute_file_hashes(pics_dst, IMG_EXTS, algo, hashes, short=(not full_hash))
        else:
            os.mkdir(pics_dst)

    # Create the video path or compute the hashes of its files
    if(include_vids):
        if(os.path.isdir(vids_dst)):
            delete_download_artifacts(vids_dst)
            hashes = compute_file_hashes(vids_dst, VID_EXTS, algo, hashes, short=(not full_hash))
        else:
            os.mkdir(vids_dst)

    # If using a full hash, prune download list based on the URL
    if(full_hash):
        stdout.write('[download_media] INFO: Pruning download list.\n')
        skipping = [name for name, url in urls.items() if any(hash in url for hash in hashes)]
        for skip in skipping:
            del urls[skip]
        stdout.write(f'[download_media] INFO: Removed {len(skipping)} downloads from the queue.\n')
    stdout.write('\n')

    len_before = len(hashes)
    hashes = multithread_download_urls_special(CoomerThread, urls, pics_dst, vids_dst, algo=algo, hashes=hashes)
    return len(hashes) - len_before


"""
Fetch a chunk of posts.
@param base - Base URL to build off of.
@param service - Service that the creator is hosted on.
@param creator - Name of the creator.
@param offset - Offset to begin from, must be divisible by 50 or None.
@return a list of posts or None.
"""
def fetch_posts(base, service, creator, offset=None):
    api_url = f'{base}/api/v1/{service}/user/{creator}'
    if(offset is not None):
        api_url = f'{api_url}?o={offset}'

    while(True):
        try:
            res = requests.get(api_url, headers={'accept': 'application/json'})
        except:
            if(res.status_code == 429 or res.status_code == 403): time.sleep(THROTTLE_TIME)
            else: break
        else:
            break

    if(res.status_code != 200):
        stdout.write(f'[fetch_posts] ERROR: Failed to fetch using API ({api_url})\n')
        stdout.write(f'[fetch_posts] ERROR: Status code: {res.status_code}\n')
        return []

    return res.json()


"""
Get a dictionary of named media in a list of posts.
@param base_url - Base URL.
@param posts - List of URLs to posts
@param imgs - Boolean for if to include images in downloading.
@param vids - Boolean for if to include videos in downloading.
"""
def parse_posts(base_url, posts, imgs, vids):
    named_urls = {}
    for post in posts:
        title = to_camel(re.sub(r'[^A-Za-z0-9\s]+', '', post['title']))
        date = re.sub('-', '', post['published'].split('T')[0])
        if('path' in post['file']):
            ext = post['file']['path'].split('.')[-1]
            if(not vids and ext in VID_EXTS): continue
            if(not imgs and ext in IMG_EXTS): continue
            name = date + '-' + title + '_0.' + ext
            named_urls[name] = f'{base_url}{post["file"]["path"]}'

        for i in range(0, len(post['attachments'])):
            attachment = post['attachments'][i]
            ext = attachment['path'].split('.')[-1]
            if(not vids and ext in VID_EXTS): continue
            if(not imgs and ext in IMG_EXTS): continue
            name = date + '-' + title + '_' + str(i+1) + '.' + ext
            named_urls[name] = f'{base_url}{attachment["path"]}'
    return named_urls


"""
Download one media.
@param url - Mostly sanitized URL of a creator's page
@param dst - Destination directory to store the downloads.
@param imgs - Boolean for if to include images in downloading.
@param vids - Boolean for if to include videos in downloading.
@param full_hash - Calculate a full hash for quick comparisons.
"""
def process_media(url, dst, imgs, vids, full_hash):
    # Further sanitize the URL
    url = re.sub('n[0-9].', '', url)

    # Use the name from the URL
    name = url.split('?f=')[-1]

    # Make the named dictionary
    named_url = {}
    named_url[name] = url

    # Download the single media
    return download_media(named_url, imgs, vids, dst, full_hash)


"""
Download all media from a creator's post.
@param url - Sanitized URL of a post.
@param dst - Destination directory to store the downloads.
@param imgs - Boolean for if to include images in downloading.
@param vids - Boolean for if to include videos in downloading.
@param full_hash - Calculate a full hash for quick comparisons.
"""
def process_post(url, dst, imgs, vids, full_hash):
    # Determine the base from the specified URL
    base_url = url[:21]

    # Get the JSON of the post
    stdout.write(f'\n[process_post] INFO: Converting post to JSON.\n')
    api_url = url.replace(base_url, f'{base_url}/api/v1')
    try:
        res = requests.get(api_url, headers={'accept': 'application/json'})
    except:
        stdout.write(f'[process_post] ERROR: Failed to fetch using API ({api_url})\n')
        return
    post = [res.json()]

    # Get the named media URLs
    stdout.write(f'\n[process_post] INFO: Parsing media from 1 post.\n')
    named_urls = parse_posts(base_url, post, imgs, vids)
    stdout.write(f'[process_post] INFO: Found {len(named_urls)} media files to download.\n\n')

    # Download all media from the posts
    return download_media(named_urls, imgs, vids, dst, full_hash)


"""
Download all media from a creator's page.
@param url - Sanitized URL of a creator's page
@param dst - Destination directory to store the downloads.
@param imgs - Boolean for if to include images in downloading.
@param vids - Boolean for if to include videos in downloading.
@param start_offs - Index to begin downloading from.
@param end_offs - Index to finish downloading from.
@param full_hash - Calculate a full hash for quick comparisons.
"""
def process_page(url, dst, imgs, vids, start_offs, end_offs, full_hash):
    # Determine the base from the specified URL
    url_sections = url.split('/')
    base_url = url[:21]

    # Round the offsets to be friendly with the API
    rounded_start = 0
    if(start_offs is not None and start_offs % POSTS_PER_FETCH != 0):
        rounded_start = start_offs - (start_offs % POSTS_PER_FETCH)
    rounded_end = maxsize
    if(end_offs is not None):
        rounded_end = end_offs - (end_offs % POSTS_PER_FETCH) + POSTS_PER_FETCH
        if(end_offs % POSTS_PER_FETCH == 0):
            rounded_end -= POSTS_PER_FETCH

    # Inform user of offset effects
    if(rounded_start != 0 or rounded_end != maxsize):
        rounded_start_str = '' if start_offs is None else str(rounded_start)
        rounded_end_str = '' if end_offs is None else str(rounded_end)
        stdout.write(f'[process_page] INFO: Fetching posts in clamped range [{rounded_start_str}, {rounded_end_str}].\n')
        start_str = '' if start_offs is None else str(start_offs)
        end_str = '' if end_offs is None else str(end_offs)
        stdout.write(f'[process_page] INFO: This will be pruned to [{start_str}, {end_str}] before downloading.\n')

    # Iterate the pages to get all posts
    all_posts = []
    offset = rounded_start
    stdout.write(f'[process_page] INFO: Fetching posts {offset + 1} - ')
    while(True):
        stdout.write(f'{offset + POSTS_PER_FETCH}...')
        stdout.flush()
        curr_posts = fetch_posts(base_url, url_sections[-3], url_sections[-1], offset=offset)
        if(curr_posts == None): return 0
        all_posts = all_posts + curr_posts
        offset += POSTS_PER_FETCH
        stdout.write(f'\033[{len(str(offset)) + 3}D')
        if(len(curr_posts) % POSTS_PER_FETCH != 0 or len(curr_posts) == 0 or offset >= rounded_end):
            break

    # Prune the download list to within the range of offsets if specified
    if(rounded_start != 0):
        skip_start = start_offs - rounded_start - 1
        all_posts = all_posts[skip_start:]
    if(rounded_end != maxsize):
        skip_end = rounded_end - end_offs
        all_posts = all_posts[:-skip_end]

    # Parse the response to get links for all media, excluding media if necessary
    stdout.write(f'\n[process_page] INFO: Parsing media from the {len(all_posts)} posts.\n')
    named_urls = parse_posts(base_url, all_posts, imgs, vids)
    stdout.write(f'[process_page] INFO: Found {len(named_urls)} media files to download.\n\n')

    # Download all media from the posts
    return download_media(named_urls, imgs, vids, dst, full_hash)


"""
Driver function to scrape media from coomer or kemono.
@param url - URL of the requested download.
@param dst - Destination directory to store the downloads.
@param imgs - Boolean for if to include images in downloading.
@param vids - Boolean for if to include videos in downloading.
@param start_offs - Index to begin downloading from.
@param end_offs - Index to finish downloading from.
@param full_hash - Calculate a full hash for quick comparisons.
"""
def main(url, dst, imgs, vids, start_offs, end_offs, full_hash):
    # Sanity check imgs and vids
    if(not imgs and not vids):
        stdout.write('[main] WARNING: Nothing to download when skipping images and videos.\n')
        return

    # Sanity check the start and end
    if(start_offs is not None and start_offs <= 0):
        stdout.write('[main] ERROR: Starting offset must be > 0.')
        return
    if(end_offs is not None):
        if(end_offs <= 0):
            stdout.write('[main] ERROR: Ending offset must be > 0.')
            return
        if(start_offs is not None and start_offs > end_offs):
            stdout.write('[main] ERROR: Ending offset must be >= starting offset.')
            return

    # Sanitize the URL
    url = 'https://www.' + re.sub(r'(www\.)|(https?://)', '', url)
    if(url[-1] == '/'): url = url[:-1]
    url_sections = url.split('/')
    if(len(url_sections) < 4):
        stderr.write('[main] ERROR: The URL is malformed.\n')
        return

    # Perform downloading of a post
    if(url_sections[-2] == 'post'):
        if(start_offs != None or end_offs != None):
            stdout.write('[main] WARNING: Start and end offsets are ignored when downloading a post.\n')
        cnt = process_post(url, dst, imgs, vids)

    # Perform downloading of a media
    elif(url_sections[-4] == 'data'):
        if(start_offs != None or end_offs != None):
            stdout.write('[main] WARNING: Start and end offsets are ignored when downloading a media.\n')
        cnt = process_media(url, dst, imgs, vids)

    # Perform downloading of a page
    else:
        cnt = process_page(url, dst, imgs, vids, start_offs, end_offs, full_hash)

    stdout.write(f'\n[main] INFO: Successfully downloaded ({cnt}) additional media.\n\n')


"""
Entry point to handle argument parsing
"""
if(__name__ == '__main__'):
    stdout.write('\n')

    parser = argparse.ArgumentParser(description='Coomer and Kemono scraper')
    parser.exit_on_error = False
    parser.add_argument('url', type=str, help='coomer or kemono URL to scrape media from')
    parser.add_argument('--out', '-o', type=str, default='./out', help='download destination (default: ./out)')
    parser.add_argument('--skip-vids', action='store_true', help='skip video downloads')
    parser.add_argument('--skip-imgs', action='store_true', help='skip image downloads')
    parser.add_argument('--confirm', '-c', action='store_true', help='confirm arguments before proceeding')
    parser.add_argument('--full-hash', action='store_true', help='calculate full hash of existing files. Ideal for a low bandwidth use case, but requires more processing')
    parser.add_argument('--offset-start', type=int, default=None, dest='start', help='starting offset to begin downloading')
    parser.add_argument('--offset-end', type=int, default=None, dest='end', help='ending offset to finish downloading')

    try:
        args = parser.parse_args()
        url = args.url
        dst = args.out
        img = args.skip_imgs
        vid = args.skip_vids
        confirm = args.confirm
        full_hash = args.full_hash
        start_offset = args.start
        end_offset = args.end

    except:
        if('--help' in argv or '-h' in argv):
            stdout.write('\n')
            exit()

        stdout.write('Falling back to reading user input\n\n')
        url = input('Enter Coomer URL: ')
        dst = input('Enter download dir (./out/): ')
        img = input('Skip images (y/N): ')
        vid = input('Skip videos (y/N): ')
        full_hash = input('Use full hash (y/N): ')
        start_offset = input('Starting offset (optional): ')
        end_offset = input('Ending offset (optional): ')
        img = len(img) > 0 and img.lower()[0] == 'y'
        vid = len(vid) > 0 and vid.lower()[0] == 'y'
        full_hash = len(full_hash) > 0 and full_hash.lower()[0] == 'y'
        if(len(dst) == 0): dst = './out'
        try:
            start_offset = None if len(start_offset) == 0 else int(start_offset)
            end_offset = None if len(end_offset) == 0 else int(end_offset)
        except:
            stdout.write("Invalid start or end offset. Exiting\n\n")
            exit()
        confirm = True
        stdout.write('\n')

    if(confirm):
        stdout.write('---\n')
        stdout.write(f'Scraping media from {url}\n')
        stdout.write(f'Media will be downloaded to {dst}\n')
        stdout.write(f'Videos will be {vid and "skipped" or "downloaded"}\n')
        stdout.write(f'Images will be {img and "skipped" or "downloaded"}\n')
        stdout.write(f'Full hashes will{full_hash and " " or " not "}be used\n')
        stdout.write(f'Starting offset is {start_offset}\n')
        stdout.write(f'Ending offset is {end_offset}\n')
        stdout.write('---\n')
        confirmed = input('Continue to download (Y/n): ')
        if(len(confirmed) > 0 and confirmed.lower()[0] != 'y'): exit()

    if(not os.path.isdir(dst)):
        os.makedirs(dst)

    main(url, dst, not img, not vid, start_offset, end_offset, full_hash)
    if(confirm):
        input('---Press enter to exit---')
        stdout.write('\n')

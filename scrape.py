from scraping_utils.scraping_utils import compute_file_hashes, DownloadThread, multithread_download_urls_special, IMG_EXTS, VID_EXTS, TOO_MANY_REQUESTS, NOT_FOUND, THROTTLE_TIME
from sys import stderr, stdout, argv
from hashlib import md5
import requests
import os
import re
import time


POSTS_PER_FETCH = 50


"""
A class to download a Coomer URL to a directory on a separate thread.
The alternate coom servers (c1, c2, ..., c6) will be swapped when "too many requests" is received as a response
"""
class CoomerThread(DownloadThread):
    # Coom server information
    C_SERVER_COUNT = 6
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
        name = self.base.split('/')[-1].split('.')[0]
        t1 = name[0:2]
        t2 = name[2:4]
        self.url = f'https://c{self.server}.coomer.su/data/{t1}/{t2}/{name}.{ext}?f={self.F_TOKEN}.{ext}'
        self.server = self.server + 1
        if(self.server > self.C_SERVER_COUNT): self.server = 1

    # Perform downloading until successful, switching coom servers as "too many requests" responses are received
    def run(self):
        ext = self.base.split('.')[-1]
        name = self.base.split('/')[-1].split('.')[0]
        media = None

        try:
            while(self.status == self.STANDBY):
                self.status = self.DOWNLOADING
                res = requests.get(self.url, allow_redirects=True)
                if(res.status_code == TOO_MANY_REQUESTS):
                    self.status = self.STANDBY
                    self.coomit()
                    if(self.server == 1):
                        time.sleep(THROTTLE_TIME)
                elif(res.status_code != NOT_FOUND):
                    media = res.content

        except requests.exceptions.Timeout:
            self.status = self.STANDBY
            self.coomit()
            if(self.server == 1):
                time.sleep(THROTTLE_TIME)

        except Exception as e:
            self.status = self.ERROR
            return

        if(media is None):
            self.status = self.ERROR
            return

        self.status = self.HASHING
        hash = self.algo(media).hexdigest()
        if(hash in self.hashes):
            self.status = self.FINISHED
            return

        self.status = self.WRITING
        self.hashes[hash] = name
        with open(os.path.join(self.dst, self.name), 'wb') as file_out:
            file_out.write(media)
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
Download media from posts on coomer.su
@param urls - Dictionary of named urls for the media of the creator.
@param include_imgs - Boolean for if to include images.
@param include_vids - Boolean for if to include videos.
@param dst - Destination directory for the downloads.
@return the total number of media entries downloaded including previous sessions.
"""
def download_media(urls, include_imgs, include_vids, dst):
    stdout.write('[download_media] INFO: Computing hashes of existing files.\n')
    hashes = {}
    pics_dst = os.path.join(dst, 'Pics');
    vids_dst = os.path.join(dst, 'Vids');

    if(include_imgs):
        if(os.path.isdir(pics_dst)):
            hashes = compute_file_hashes(pics_dst, IMG_EXTS, md5, hashes)
        else:
            os.mkdir(pics_dst)

    if(include_vids):
        if(os.path.isdir(vids_dst)):
            hashes = compute_file_hashes(vids_dst, VID_EXTS, md5, hashes)
        else:
            os.mkdir(vids_dst)

    stdout.write('\n')

    hashes = multithread_download_urls_special(CoomerThread, urls, pics_dst, vids_dst, algo=md5, hashes=hashes)
    return len(hashes)


"""
Fetch a chunk of posts.
@param service - Service that the creator is hosted on.
@param creator - Name of the creator.
@param offset - Offset to begin from, must be divisible by 50 or None.
@return a list of posts
"""
def fetch_posts(service, creator, offset=None):
    api_url = f'https://coomer.su/api/v1/{service}/user/{creator}'
    if(offset is not None):
        api_url = f'{api_url}?o={offset}'

    while(True):
        try: res = requests.get(api_url, headers={'accept': 'application/json'})
        except: pass

        if(res.status_code == 429): time.sleep(THROTTLE_TIME)
        else: break

    if(res.status_code != 200):
        stdout.write(f'[fetch_posts] ERROR: Failed to fetch using API ({api_url})\n')
        stdout.write(f'[fetch_posts] ERROR: Status code: {res.status_code}\n')
        return []

    return res.json()


"""
Driver function to scrape coomer.su creators.
@param url - URL of the creator, not a specific post.
@param dst - Destination directory to store the downloads.
@param imgs - Boolean for if to include images in downloading.
@param vids - Boolean for if to include videos in downloading.
"""
def main(url, dst, imgs, vids):
    # Sanity check imgs and vids
    if(not imgs and not vids):
        stdout.write('[main] WARNING: Nothing to download when skipping images and videos.\n')
        return

    # Sanitize the URL
    url = 'https://www.' + re.sub('(www\.)|(https?://)', '', url)
    if(url[-1] == '/'): url = url[:-1]
    url_sections = url.split('/')
    if(len(url_sections) < 4):
        stderr.write('[main] ERROR: The URL is malformed.\n')
        return
    if(url_sections[-2] == 'post'):
        stderr.write('[main] ERROR: The URL must be for a creator, not a specific post.\n')
        return
    elif(url_sections[-4] == 'data'):
        stderr.write('[main] ERROR: The URL must be for a creator, not a specific media.\n')
        return

    # Iterate the pages to get all posts
    all_posts = []
    offset = 0
    stdout.write(f'[main] INFO: Fetching posts {offset + 1} - ')
    while(True):
        stdout.write(f'{offset + POSTS_PER_FETCH}...')
        stdout.flush()
        curr_posts = fetch_posts(url_sections[-3], url_sections[-1], offset=offset)
        all_posts = all_posts + curr_posts
        offset += POSTS_PER_FETCH
        stdout.write(f'\033[{len(str(offset)) + 3}D')
        if(len(curr_posts) % POSTS_PER_FETCH != 0):
            break
        elif(len(curr_posts) == 0):
            stdout.write(f'{offset - POSTS_PER_FETCH}...')
            break

    # Parse the response to get links for all media, excluding media if necessary
    stdout.write(f'\n[main] INFO: Parsing media from the {len(all_posts)} posts.\n')
    named_urls = {}
    base = 'http://www.coomer.su'
    for post in all_posts:
        title = to_camel(re.sub(r'[^A-Za-z0-9\s]+', '', post['title']))
        date = re.sub('-', '', post['published'].split('T')[0])
        if('path' in post['file']):
            ext = post['file']['path'].split('.')[-1]
            if(not vids and ext in VID_EXTS): continue
            if(not imgs and ext in IMG_EXTS): continue
            name = date + '-' + title + '_0.' + ext
            named_urls[name] = f'{base}{post["file"]["path"]}'

        for i in range(0, len(post['attachments'])):
            attachment = post['attachments'][i]
            ext = attachment['path'].split('.')[-1]
            if(not vids and ext in VID_EXTS): continue
            if(not imgs and ext in IMG_EXTS): continue
            name = date + '-' + title + '_' + str(i+1) + '.' + ext
            named_urls[name] = f'{base}{attachment["path"]}'

    stdout.write(f'[main] INFO: Found {len(named_urls)} media files to download.\n\n')

    # Download all media from the posts
    cnt = download_media(named_urls, imgs, vids, dst)
    stdout.write(f'\n[main] INFO: Successfully downloaded ({cnt}) unique media.\n\n')


"""
Entry point
"""
if(__name__ == '__main__'):
    stdout.write('\n')
    if(len(argv) != 5):
        url = input('Enter Coomer URL: ')
        dst = input('Enter download dir (./out/): ')
        img = input('Include images (Y/n): ')
        vid = input('Include videos (Y/n): ')
        stdout.write('\n')
    else:
        url = argv[1]
        dst = argv[2]
        img = argv[3]
        vid = argv[4]

    if(len(img) == 0): img = 'y'
    else: img = img.lower()[0]

    if(len(vid) == 0): vid = 'y'
    else: vid = vid.lower()[0]

    if(len(dst) == 0):
        dst = './out'
    if(not os.path.isdir(dst)):
        os.makedirs(dst)

    main(url, dst, (img == 't' or img == 'y'), (vid == 't' or vid == 'y'))
    input('---Press enter to exit---')
    stdout.write('\n')

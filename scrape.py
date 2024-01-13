from scraping_utils.scraping_utils import compute_file_hashes, DownloadThread, multithread_download_urls_special, IMG_EXTS, VID_EXTS, TOO_MANY_REQUESTS, NOT_FOUND, THROTTLE_TIME
from sys import stdout, argv
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
    def __init__(self, url, dst, algo=md5, hashes={}):
        DownloadThread.__init__(self, url, dst, algo, hashes)
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
            print(e)
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
        with open(os.path.join(self.dst, hash + '.' + ext), 'wb') as file_out:
            file_out.write(media)
        self.status = self.FINISHED


"""
Download media from posts on coomer.su
@param urls - List of urls for the media of the creator.
@param include_vids - Boolean for if to include videos.
@param dst - Destination directory for the downloads. Videos to be stored in a sub-directory.
@return the total number of media entries downloaded including previous sessions.
"""
def download_media(urls, include_vids, dst):
    stdout.write('[download_media] INFO: Computing hashes of existing files.\n')
    hashes = {}
    pics_dst = os.path.join(dst, 'Pics');
    vids_dst = os.path.join(dst, 'Vids');
    
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
    try:
        api_url = 'https://coomer.su/api/v1/%s/user/%s' % (service, creator)
        if(offset is not None):
            api_url = '%s?o=%d' % (api_url, offset)
        res = requests.get(api_url, headers={'accept': 'application/json'})
        assert(res.status_code == 200)
        return res.json()
    except:
        stdout.write('[fetch_posts] ERROR: Failed to fetch using API (%s)\n' % api_url)
        stdout.write('[fetch_posts] ERROR: Status code: %d\n' % res.status_code)
        return []


"""
Driver function to scrape coomer.su creators.
@param url - URL of the creator, not a specific post.
@param dst - Destination directory to store the downloads.
@param vids - Boolean for if to include videos in downloading.
"""
def main(url, dst, vids):
    # Sanitize the URL
    url = 'https://www.' + re.sub('(www\.)|(https?://)', '', url)
    if(url[-1] == '/'): url = url[:-1]
    url_sections = url.split('/')
    if(url_sections[-2] == 'post'):
        stdout.write('[main] INFO: The URL must be for a creator, not a specific post.\n')
        return
    elif(url_sections[-4] == 'data'):
        stdout.write('[main] INFO: The URL must be for a creator, not a specific media.\n')
        return
        
    # Iterate the pages to get all posts
    all_posts = []
    offset = 0
    while(True):
        stdout.write('[main] INFO: Fetching posts %d - %d...\n' % (offset + 1, offset + POSTS_PER_FETCH))
        curr_posts = fetch_posts(url_sections[-3], url_sections[-1], offset=offset)
        all_posts = all_posts + curr_posts
        offset += POSTS_PER_FETCH
        if(len(curr_posts) % POSTS_PER_FETCH != 0):
            stdout.write('[main] INFO: Final post fetch completed!\n')
            break
        elif(len(curr_posts) == 0):
            stdout.write('[main] INFO: Attempted to fetch more posts than existed. Moving on...\n')
            break
        
    # Parse the response to get links for all media, excluding videos if necessary
    stdout.write('[main] INFO: Parsing media from the %d posts.\n' % (len(all_posts)))
    urls = []
    base = 'http://www.coomer.su'
    for post in all_posts:
        if('path' in post['file']):
            ext = post['file']['path'].split('.')[-1]
            if(not vids and ext in VID_EXTS): continue
            urls.append('%s%s' % (base, post['file']['path']))
        for attachment in post['attachments']:
            ext = attachment['path'].split('.')[-1]
            if(not vids and ext in VID_EXTS): continue
            urls.append('%s%s' % (base, attachment['path']))
    stdout.write('[main] INFO: Found %d media files to download.\n\n' % (len(urls)))
    
    # Download all media from the posts
    cnt = download_media(urls, vids, dst)
    stdout.write('\n')
    stdout.write('[main] INFO: Successfully downloaded (%d) unique media.\n\n' % (cnt))


"""
Entry point
"""
if(__name__ == '__main__'):
    stdout.write('\n')
    if(len(argv) != 4):
        url = input('Enter Coomer URL: ')
        dst = input('Enter download dir (./out/): ')
        vid = input('Include videos (Y/N): ')
    else:
        url = argv[1]
        dst = argv[2]
        vid = argv[3]
        
    vid = vid.lower()[0]
    
    if(len(dst) == 0):
        dst = './out'
    if(not os.path.isdir(dst)):
        os.mkdir(dst)
        
    main(url, dst, (vid == 't' or vid == 'y'))
    input('---Press enter to exit---')
    stdout.write('\n')

from scraping_utils.scraping_utils import compute_file_hashes, download_urls
from bs4 import BeautifulSoup
from sys import stdout, argv
from hashlib import md5
from threading import Thread, active_count
import requests 
import time
import os
import re
import math


IMG_EXTS = [ 'jpg', 'jpeg', 'png', 'gif' ]
VID_EXTS = [ 'mp4', 'm4v']
PER_PAGE = 50
MAX_THREADS = 8


"""
A class to download a URL to a directory on a separate thread.
"""
class DownloadThread(Thread):
    def __init__(self, url, dst, hashes):
        Thread.__init__(self)
        self.url = url
        self.dst = dst
        self.hashes = hashes
    
    def run(self):
        self.is_alive = True
        self.hashes = download_urls(self.dst, [self.url], hashes=self.hashes)
        self.is_alive = False


"""
Get a list of post links for a given coomer.party page.
@param page - Page for coomer.party
@return a list of entries.
"""
def fetch_page_entries(page):
    ret = []
    tags = page.find_all('article', class_='post-card')
    for post in tags:
        link = post.find('a')['href']
        ret.append(link)
        stdout.write('[fetch_page_entries] Discovered entry: %s\n' % (link))
    return ret


"""
Iterate the pages of coomer.party to get all posts for a creator.
@param url - Base URL for the creator.
@param main_page - Starting page for the creator.
@param last_page - Number of pages for the creator.
@return a list of all posts for the creator.
"""
def iterate_pages(url, main_page, max_offset):
    ret = []
    curr_offset = 0
    curr_page = main_page
    success = False
    while(curr_offset <= max_offset):
        stdout.write('[iterate_pages] INFO: Parsing page %d...\n' % (curr_offset / PER_PAGE + 1))
        ret = ret + fetch_page_entries(curr_page)
        curr_offset = curr_offset + PER_PAGE
        time.sleep(3)
        while(not success):
            try:
                res = requests.get(url + '?o=' + str(curr_offset))
                success = True
            except:
                stdout.write('[iterate_pages] ERROR: Failed page %d. Retrying.\n' % (curr_offset / PER_PAGE + 1))
        success = False
        curr_page = BeautifulSoup(res.content, 'html.parser')
    return ret


"""
Determine the download directory based on the extension of a URL
@param url - URL to use for reference.
@param pics_dst - Destination if URL is for a picture.
@param vids_dst - Destination if URL is for a video.

"""
def get_download_dst(url, pics_dst, vids_dst):
    for ext in VID_EXTS:
        if url.endswith(ext):
            return vids_dst
    return pics_dst


"""
Orchestrate multi-threaded downloads.
@param urls - List of urls to download.
@param pics_dst - Destination for pictures.
@param vids_dst - Destination for videos.
@param hashes - Dictionary of hashes for existing downloaded media.
@return the updated hash table.
"""
def multithread_download(urls, pics_dst, vids_dst, hashes):
    stdout.write('[multithread_download] INFO: Downloading %d urls.\n' % (len(urls)))
    threads = []
    pos = 0
    for i in range(0, MAX_THREADS):
        if(pos >= len(urls)):
            break
        thread_url = urls[pos]
        thread_dst = get_download_dst(thread_url, pics_dst, vids_dst)
        threads.append(DownloadThread(thread_url, thread_dst, hashes))
        threads[-1].start()
        pos = pos + 1

    while(pos < len(urls)):
        for thread in threads:
            if(not thread.is_alive):
                hashes.update(thread.hashes)
                thread_url = urls[pos]
                thread_dst = get_download_dst(thread_url, pics_dst, vids_dst)
                thread = DownloadThread(thread_url, thread_dst, hashes);
                thread.start()
                pos = pos + 1
                if(pos >= len(urls)):
                    break
        time.sleep(3)
    
    waiting = active_count() - 1
    while(waiting > 0):
        waiting = active_count() - 1
        if(waiting > 0):
            print("[multithread_download] INFO: Still downloading %d media.\n" % (waiting))
            time.sleep(10)
    
    return hashes


"""
Download media from posts on coomer.party
@param url - Base URL for the creator.
@param posts - List of posts for the creator.
@param include_vids - Boolean for if to include videos.
@param dst - Destination directory for the downloads. Videos to be stored in a sub-directory.
@return the total number of media entries downloaded including previous sessions.
"""
def download_media(url, posts, include_vids, dst):
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
    url_list = []
    for post in posts:
        stdout.write('[download_media] INFO: Processing (%s)\n' % post)
        res = requests.get('https://coomer.party' + post.strip())
        page = BeautifulSoup(res.content, 'html.parser')
        try:
            img_parents = page.find('div', class_='post__files').find_all('a')
        except:
            img_parents = []
            
        for parent in img_parents:
                src = parent['href']
                url_list.append(src)
        
        if(include_vids):
            try:
                vid_parents = page.find('ul', class_='post__attachments').find_all('a')
            except:
                vid_parents = []
            
            for parent in vid_parents:
                src = parent['href']
                url_list.append(src)
                
        time.sleep(1)
        
    hashes = multithread_download(url_list, pics_dst, vids_dst, hashes)
    return len(hashes)


"""
Driver function to scrape coomer.party creators.
@param url - URL of the creator, not a specific post.
@param dst - Destination directory to store the downloads.
@param vids - Boolean for if to include videos in downloading.
"""
def main(url, dst, vids):
    # Sanitize the URL
    url = 'https://www.' + re.sub('(www\.)|(https?://)', '', url)
    url_sections = url.split('/')
    if(url_sections[-2] == 'post'):
        stdout.write('[main] INFO: The URL must be for a creator, not a specific post.\n')
        return
    elif(url_sections[-4] == 'data'):
        stdout.write('[main] INFO: The URL must be for a creator, not a specific media.\n')
        return
        
    # Get the main page
    try:
        res = requests.get(url)
        main_page = BeautifulSoup(res.content, 'html.parser')
    except:
        stdout.write('[main] INFO: Failed to fetch from (%s).\n' % url)
        stdout.write('[main] INFO: Confirm that there are no mistakes with the given URL.\n')
        return
        
    # Calculate the number of pages and posts
    try:
        total_posts = main_page.find(id='paginator-top').find('small').text
        max_page = math.ceil(int(total_posts.split('of ')[-1]) / PER_PAGE)
        max_offset = PER_PAGE * (max_page - 1)
        stdout.write('[main] INFO: Discovered %d pages.\n' % max_page)
    except:
        max_offset = 1
        max_page = 1
        stdout.write('[main] INFO: Discovered %d page.\n' % max_page)
        
    # Iterate the pages to get all post links
    posts = iterate_pages(url, main_page, max_offset)
    
    # Download all media from the posts
    cnt = download_media(url, posts, vids, dst)
    stdout.write('[main] INFO: Successfully downloaded (%d) pieces of media.\n' % (cnt))


"""
Entry point
"""
if(__name__ == '__main__'):
    stdout.write('\n')
    if(len(argv) != 4):
        stdout.write('USAGE: %s <url> <download_dir> <include_videos>\n' % (argv[0]))
    else:
        if(not os.path.isdir(argv[2])):
            os.mkdir(argv[2])
        argv[3] = argv[3].lower()[0]
        main(argv[1], argv[2], (argv[3] == 't' or argv[3] == 'y'))
    stdout.write('\n')

from scraping_utils.scraping_utils import compute_file_hashes, download_urls
from bs4 import BeautifulSoup
from sys import stdout, argv
from hashlib import md5
import requests 
import time
import os
import re


IMG_EXTS = [ 'jpg', 'jpeg', 'png', 'gif' ]
VID_EXTS = [ 'mp4', 'm4v']


"""
Get a list of post links for a given coomer.party page.
@param page - Page for coomer.party
@return a list of entries.
"""
def fetch_page_entries(page):
    ret = []
    tags = page.find_all('h2', class_='post-card__heading')
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
    while(curr_offset <= max_offset):
        stdout.write('[iterate_pages] INFO: Parsing page %d...\n' % (curr_offset / 25 + 1))
        ret = ret + fetch_page_entries(curr_page)
        curr_offset = curr_offset + 25
        time.sleep(1)
        res = requests.get(url + '?o=' + str(curr_offset))
        curr_page = BeautifulSoup(res.content, 'html.parser')
    return ret


"""
Download media from posts on coomer.party
@param url - Base URL for the creator.
@param posts - List of posts for the creator.
@param include_vids - Boolean for if to include videos.
@param dst - Destination directory for the downloads. Videos to be stored in a sub-directory.
@return the total number of media entries downloaded.
"""
def download_media(url, posts, include_vids, dst):
    stdout.write('[download_media] INFO: Computing hashes of existing files.\n')
    hashes = {}
    pics_dst = os.path.join(dst, 'pics');
    vids_dst = os.path.join(dst, 'vids');
    if(os.path.isdir(pics_dst)):
        hashes = compute_file_hashes(pics_dst, IMG_EXTS, md5, hashes)
    else:
        os.mkdir(pics_dst)
    if(include_vids):
        if(os.path.isdir(vids_dst)):
            hashes = compute_file_hashes(vids_dst, VID_EXTS, md5, hashes)
        else:
            os.mkdir(vids_dst)
        
    for post in posts:
        stdout.write('[download_media] INFO: Processing (%s)\n' % post)
        res = requests.get('https://coomer.party' + post.strip())
        page = BeautifulSoup(res.content, 'html.parser')
        try:
            img_parents = page.find('div', class_='post__files').find_all('a')
        except:
            stdout.write('[download_media] INFO: No images found.\n')
            img_parents = []
            
        img_urls = []
        for parent in img_parents:
                src = 'https://www.coomer.party' + parent['href']
                img_urls.append(src)
        
        if(include_vids):
            try:
                vid_parents = page.find('ul', class_='post__attachments').find_all('a')
            except:
                stdout.write('[download_media] INFO: No videos found.\n')
                vid_parents = []
                
            vid_urls = []
            for parent in vid_parents:
                src = 'https://c4.coomer.party' + parent['href']
                vid_urls.append(src)
            
        hashes = download_urls(pics_dst, img_urls, hashes=hashes)
        if(include_vids):
            hashes = download_urls(vids_dst, vid_urls, hashes=hashes)
        
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
        next_button = main_page.find(title='Next page').parent
        max_page = next_button.find_previous('li').find("a")['href']
        max_offset = int(str(max_page).split('=')[-1])
        max_page = max_offset / 25 + 1
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
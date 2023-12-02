from scraping_utils.scraping_utils import compute_file_hashes, download_urls, multithread_download_urls, IMG_EXTS, VID_EXTS
from sys import stdout, argv
from hashlib import md5
import requests 
import os
import re


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
        
    hashes = multithread_download_urls(urls, pics_dst, vids_dst, hashes=hashes)
    return len(hashes)


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
          
    # Craft the API URL and perform a GET request
    try:
        api_url = f'https://coomer.su/api/v1/{url_sections[-3]}/user/{url_sections[-1]}'
        res = requests.get(api_url, headers={'accept': 'application/json'})
        assert(res.status_code == 200)
    except:
        stdout.write('[main] INFO: Failed to fetch using API (%s)\n' % api_url)
        stdout.write('[main] INFO: Status code: %d\n' % res.status_code)
        return
        
    # Parse the response to get links for all media, excluding videos if necessary
    urls = []
    base = 'http://www.coomer.su'
    for post in res.json():
        if('path' in post['file']):
            ext = post['file']['path'].split('.')[-1]
            if(not vids and ext in VID_EXTS): continue
            urls.append('%s%s' % (base, post['file']['path']))
        for attachment in post['attachments']:
            ext = attachment['path'].split('.')[-1]
            if(not vids and ext in VID_EXTS): continue
            urls.append('%s%s' % (base, attachment['path']))
    
    # Download all media from the posts
    cnt = download_media(urls, vids, dst)
    stdout.write('[main] INFO: Successfully downloaded (%d) pieces of media.\n' % (cnt))


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
        vid = argv[3].lower()[0]
    
    if(len(dst) == 0):
        dst = './out'
    if(not os.path.isdir(dst)):
        os.mkdir(dst)
        
    main(url, dst, (vid == 't' or vid == 'y'))
    input('---Press any key to exit---')
    stdout.write('\n')

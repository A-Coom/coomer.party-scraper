import argparse
import logging
import os
import sys
from pathlib import Path
from typing import List, Tuple, Any

from .coom import main as coom_main
from .utils import sanitize_url


logger = logging.getLogger(__name__)


"""
Parse the program arguments or read them from stdin
"""
def get_arguments() -> tuple[list[str] | Any, Path, str | bool | Any, str | bool | Any, tuple[
    Any | None, Any | None], bool | Any, Any, int | Any]:
    # Initialize arguments for CLI use
    parser = argparse.ArgumentParser(description='Coomer and Kemono scraper')
    parser.exit_on_error = False
    parser.add_argument('urls', type=str, nargs='*', help='coomer or kemono URLs to scrape media from, separated by a space')
    parser.add_argument('-c', '--confirm', action='store_true', help='confirm arguments before proceeding')
    parser.add_argument('--dump-urls', action='store_true', help='print the urls to a text file instead of downloading')
    parser.add_argument('-j', '--jobs', type=int, default=4, help='number of concurrent download threads (default: 4)')
    parser.add_argument('--log-file', type=str, default=None, help='direct logs to a file instead of stdout')
    parser.add_argument('--log-level', type=str, default=None, help='level of logging (DEBUG, INFO, WARNING, ERROR; default: INFO)')
    parser.add_argument('--offset-end', type=int, default=None, dest='end', help='ending offset to finish downloading')
    parser.add_argument('--offset-start', type=int, default=None, dest='start', help='starting offset to begin downloading')
    parser.add_argument('-o', '--out', type=str, default=os.getcwd(), help='download destination (default: CWD)')
    parser.add_argument('--skip-imgs', action='store_true', help='skip image downloads')
    parser.add_argument('--skip-vids', action='store_true', help='skip video downloads')
    #new flags
    parser.add_argument('--rate-limit', type=int, default=2, help='rate limit in requests/s (default: 2)')
    parser.add_argument('--template', type=str, default=None, help='<tags>')
    parser.add_argument('--image-template', type=str, default=None, help='<tags>')
    parser.add_argument('--video-template', type=str, default=None, help='<tags>')
    # Handle the special case of logging data
    log_file = None
    log_lvl = logging.INFO
    try:
        args = parser.parse_args()
        log_file = args.log_file
        log_lvl_str = args.log_level.upper()
        if log_lvl_str is not None:
            assert log_lvl_str in ['DEBUG', 'INFO', 'WARNING', 'ERROR'], f'Unknown log level "{log_lvl_str}"'
            if log_lvl_str == 'DEBUG':
                log_lvl = logging.DEBUG
            elif log_lvl_str == 'INFO':
                log_lvl = logging.INFO
            elif log_lvl_str == 'WARNING':
                log_lvl = logging.WARNING
            elif log_lvl_str == 'ERROR':
                log_lvl = logging.ERROR
    except AssertionError as e:
        print(f'AssertionError: {e}')
        parser.print_help(sys.stderr)
        exit()
    except argparse.ArgumentError as e:
        print(f'ArgumentError: {e}')
        parser.print_help(sys.stderr)
        exit()
    except Exception:
        pass
    logging.basicConfig( filename=log_file, filemode='w', level=log_lvl
                       , format='[%(levelname)s %(asctime)s] (%(module)s) %(message)s'
                       , datefmt='%Y-%m-%d %H:%M:%S' )
    logger.info('Initialized logger')
    
    # Assume non-interactive usage
    try:
        args = parser.parse_args()
        if '--help' in sys.argv or '-h' in sys.argv:
            parser.print_help(sys.stderr)
            exit()
        urls = args.urls
        dst = args.out
        skip_img = args.skip_imgs
        skip_vid = args.skip_vids
        confirm = args.confirm
        offs_start = args.start
        offs_end = args.end
        dump_urls = args.dump_urls
        jobs = args.jobs
        rate_limit = args.rate_limit
        template = args.template
        image_template = args.image_template
        video_template = args.video_template

        assert len(urls) > 0
        logger.debug('Usage: non-interactive')

    # Fallback to interactive usage
    except AssertionError:
        logger.debug('Usage: interactive')
        urls = [ input('Enter Coomer URL: ') ]
        dst = input(f'Enter download dir (default: {os.getcwd()}): ')
        skip_img = input('Skip images (y/N): ')
        skip_vid = input('Skip videos (y/N): ')
        skip_img = skip_img and skip_img.lower()[0] == 'y'
        skip_vid = skip_vid and skip_vid.lower()[0] == 'y'
        dst = dst if dst else os.getcwd()
        offs_start = None
        offs_end = None
        dump_urls = False
        confirm = True
        rate_limit = input('Enter rate limit in req/s (default: 2): ')
        rate_limit = int(rate_limit) if rate_limit.isdigit() else 2
        template = None
        image_template = None
        video_template = None

    # Allow the user to confirm information
    if confirm:
        print()
        logger.info(f'Scraping media from {urls}')
        logger.info(f'Media will be downloaded to {dst}')
        logger.info(f'Videos will be {skip_vid and "skipped" or "downloaded"}')
        logger.info(f'Images will be {skip_img and "skipped" or "downloaded"}')
        logger.info(f'Starting offset is {offs_start}')
        logger.info(f'Ending offset is {offs_end}')
        logger.info(f'There will be {jobs} concurrent download threads')
        logger.info(f'Rate limit is {rate_limit} requests/s')
        if template:
            logger.info(f'Using custom template: {template}')
        if image_template:
            logger.info(f'Using image template {image_template}')
        if video_template:
            logger.info(f'Using video template {video_template}')
        print()
        confirmed = input('Continue to download (Y/n): ')
        if len(confirmed) > 0 and confirmed.lower()[0] != 'y':
            exit()

    # Return parsed arguments
    return urls, Path(dst), skip_img, skip_vid, (offs_start, offs_end), dump_urls, jobs, rate_limit, template, image_template, video_template



"""
Driver function to handle argument parsing and sanity checks before going to coomer-specific details
"""

def main():
    # Get the program arguments or read them from stdin
    urls, dst, skip_img, skip_vid, offsets, dump_urls, jobs, rate_limit, template, image_template, video_template= get_arguments()

    # Sanity check skip flags
    if skip_img and skip_vid:
        logger.warning('Nothing to download when skipping images and videos')
        return

    # Sanity check offsets
    if offsets[0] is not None and offsets[0] <= 0:
        logger.error('Starting offset must be > 0')
        return
    if offsets[1] is not None:
        if offsets[1] <= 0:
            logger.error('Ending offset must be > 0')
            return
        if offsets[0] is not None and offsets[0] > offsets[1]:
            logger.error('Ending offset must be >= starting offset')
            return

        if image_template or video_template and not template:
            logger.error('Media-specific templates require a base template to be set')
            return

    # Sanitize argument URLs
    urls = [ sanitize_url(u) for u in urls ]

    # Proceed with coomer-specific details...
    coom_main(urls, dst, skip_img, skip_vid, offsets, dump_urls, jobs, rate_limit, template, image_template, video_template)
    


"""
Entry point to handle argument parsing
"""
if __name__ == '__main__':
    main()
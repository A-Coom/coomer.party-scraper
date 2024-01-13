# Coomer.Party (Coomer.su) Scraper / Downloader
A coomer.party scraper to download all media from a specified artist using a multithreading orchestrator in Python.

# Usage
The easiest route is to download the latest release, run the executable, and follow the prompts.

## IMPORTANT
Before using a wrapper or the platform agnositic command below, you must intialize the `scraping_utils` submodule. To do this, run the following command while in the repository directory: `git clone https://github.com/A-Coom/scraping_utils.git`

If you are experiencing multiple failed attempts to load a page, please confirm that you are not accessing coomer.party (or coomer.su) in any way aside from this scraper. For example, if you have this scraper running on a laptop and the website open on your phone, you are more likely to be blocked from the website temporarily. If this occurs, close all connections to the website, including the scraper. After waiting about five minutes, you should be able to begin scraping again.

## Platform Agnositic
`python3 ./scraper.py <url> <download_dir> <include_videos>`
* `url` - URL for the creator of interest.
* `download_dir` - Destination directory for the media to be saved to.
* `include_videos` - If true, videos will also be saved.

The URL must be the landing page for a specific artist. It may not be a post for an artist. It should also be noted that downloading videos takes a significantly longer time than a single image.

## Wrappers
Wrapper scripts for specific platforms are available in `bin/`. If you do not see a wrapper script for your platform of choice, please use the platform agnostic approach described above. Wrapper scripts are accepted via pull requests.

# Requirements
In its current state, this scraper requires: requests.

You can install these requirements by using:

`python3 -m pip install -r requirements.txt`

For more information on the individual requirements and how to install them manually, see below.

### Requests
`python3 -m pip install requests`

This is required to send the network requests to query the target website and download the media.

# A Note on Scraping
It is entirely possible that this will not work in the future. Web scraping is fragile in that if the layout of the webpage changes, then any scraping tool may parse the new page incorrectly. This version is confirmed to work as of January 13, 2024. This approach uses the API, which should not break in the near future. Nevertheless, if you encounter any problems after the aformentioned date, please open an issue.

# Disclaimer
The website that this scraper targets is known to host media that is taken from a pay-per-view service without the consent of the original owner. By accessing this website (through a web browser or the scraper), you are willfully viewing this stolen media. The user of the scraper is fully responsible for any consequences that may occur from these actions, and the developer of this scraper is not responsible for how the user chooses to act.

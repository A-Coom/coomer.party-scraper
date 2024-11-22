# Coomer ans Kemono Scraper / Downloader

A scraper to download all media from coomer.su and kemono.su (previously coomer.party and kemono.party) uploaded by a specified artist using a multithreading orchestrator in Python.

![output](./img/output.jpg)



## Usage
The easiest route is to download the latest release for your platform, run the executable, and follow the prompts.

If a release is not available for your platform, follow the platform agnostic approach



## Platform Agnostic Usage

The platform agnostic usage requires Python 3 to be installed on your system. If a release for your platform is available, use the executable file for easier usage.



### Submodule Dependency

Before using the platform agnostic command below, you must initialize the `scraping_utils` submodule. To do this, run the following command while in the repository directory: `git clone https://github.com/A-Coom/scraping_utils.git`



### Requirements
In its current state, this scraper requires the requests package. You can install this requirement by executing the following command in the repository directory:

`python3 -m pip install -r requirements.txt`



### Execution Command
```
usage: scrape.py [-h] [--out OUT] [--skip-vids] [--skip-imgs] [--confirm]
                 [--start-offset START_OFFSET] [--end-offset END_OFFSET]
                 url

Coomer and Kemono scraper

positional arguments:
  url                   coomer or kemono URL to scrape media from

optional arguments:
  -h, --help            show this help message and exit
  --out OUT, -o OUT     download destination (default: ./out)
  --skip-vids           skip video downloads
  --skip-imgs           skip image downloads
  --confirm, -c         confirm arguments before proceeding
  --start-offset START  starting offset to begin downloading
  --end-offset END      ending offset to finish downloading

```

The URL can be a page for an artist, a post from an artist, or a single media file. The starting and ending offsets are only respected when downloading from a page.

If any of the parameters are omitted, then you will be prompted for all parameters during execution.



## A Note on Scraping
This version is confirmed to work as of November 22, 2024. This approach uses the API when possible, which increases the reliability that it will continue to work in the future. Nevertheless, if you encounter any problems, please open an issue.



## Disclaimer
The website that this scraper targets is known to host media that is taken from many pay-per-view services without the consent of the original owner. By accessing this website (through a web browser or this tool), you are willfully viewing this stolen media. The user of the scraper is fully responsible for any consequences that may occur from these actions, and the developer(s) of this scraper does not assume responsibility for how the user chooses to act.

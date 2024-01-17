# Coomer.Party (Coomer.su) Scraper / Downloader

A coomer.party scraper to download all media from a specified artist using a multithreading orchestrator in Python.

![output](./img/output.jpg)



## Usage
The easiest route is to download the latest release for your platform, run the executable, and follow the prompts.

If a release is not available for your platform, follow the platform agnostic approach



## Platform Agnostic Usage

### Submodule Dependency

Before using the platform agnostic command below, you must initialize the `scraping_utils` submodule. To do this, run the following command while in the repository directory: `git clone https://github.com/A-Coom/scraping_utils.git`

### Requirements
In its current state, this scraper requires the requests package. You can install this requirement by executing the following command in the repository directory:

`python3 -m pip install -r requirements.txt`

### Execution Command
`python3 ./scraper.py <url> <download_dir> <include_videos>`
* `url` - URL for the creator of interest.
* `download_dir` - Destination directory for the media to be saved to.
* `include_videos` - If true, videos will also be saved.

The URL must be the landing page for a specific artist. It may not be a post for an artist.

If any of the parameters are omitted, then you will be prompted for all parameters during execution.



## A Note on Scraping
This version is confirmed to work as of January 17, 2024. This approach uses the API when possible, which increases the reliability that it will continue to work in the future. Nevertheless, if you encounter any problems, please open an issue.



## Disclaimer
The website that this scraper targets is known to host media that is taken from many pay-per-view services without the consent of the original owner. By accessing this website (through a web browser or this tool), you are willfully viewing this stolen media. The user of the scraper is fully responsible for any consequences that may occur from these actions, and the developer(s) of this scraper does not assume responsibility for how the user chooses to act.

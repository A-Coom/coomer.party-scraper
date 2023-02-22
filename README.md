# Coomer.Party Scraper
A coomer.party scraper to download all media from a specified artist.

# Usage
`python3 ./scraper.py <url> <download_dir> <include_videos>`
* `url` - URL for the creator of interest.
* `download_dir` - Destination directory for the media to be saved to.
* `include_videos` - If true, videos will also be saved.

The URL must be the landing page for a specific artist. It may not be a post for an artist. It should also be noted that downloading videos takes a significantly longer time than a single image.

# Requirements
In its current state, this scraper requires: requests and bs4.

You can install these requirements by using:

`python3 -m pip install -r requirements.txt`

For more information on the individual requirements and how to install them manually, see below.

### Requests
`python3 -m pip install requests`

This is required to send the network requests to query the target website and download the media.

### bs4
`python3 -m pip install bs4`

This is required to parse the webpage more easily. This requirement is planned to be removed in the future.

# Disclaimer
The website that this scraper targets is known to host media that is taken from a pay-per-view service without the consent of the original owner. By accessing this website (through a web browser or the scraper), you are willfully viewing this stolen media. The user of the scraper is fully responsible for any consequences that may occur from these actions, and the developer of this scraper is not responsible for how the user chooses to act.

#!/bin/bash
#Author: Marcel
#Date:2023
#Description: Script to automatically run the download for a number of pages


#Globals 
PYTHON="python3"
VIDEO_FLAG="include_videos"

BASE_URL=""
PAGE_URL=""

START_PAGE=0
NUM_PAGES=0
PAGE_INDEX=0


function get_base_url () {
    echo "Please enter the base URL:"
    read BASE_URL
}

function get_dest_path () {
    echo "Please enter destination path:"
    read DEST
}

#Function to get number of pages from user
function get_num_pages () {
    echo "Please enter the number of pages:"
    read NUM_PAGES

    echo "Please enter start page num:"
    read START_PAGE
}


function calculate_url () {
    if [ ${PAGE_INDEX} -eq 1 ]; then
        PAGE_URL=${BASE_URL}
    else
        IMGS=$((50 * ${PAGE_INDEX}))
        PAGE_URL="${BASE_URL}?o=${IMGS}" 
    fi
}

function call_program () {
    get_base_url
    get_dest_path
    get_num_pages

    
    #for i in {0..20}
    for ((i = ${START_PAGE} ; i <= ${NUM_PAGES} ; i++));
    do
        PAGE_INDEX=${i}
        calculate_url
        echo "Downloading for page: ${i} with url: ${PAGE_URL}"
        ${PYTHON} ./scrape.py ${PAGE_URL} ${DEST} ${VIDEO_FLAG}
    done
}

call_program


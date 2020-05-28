import os
import sys
import time
import twitter
import json
import praw
import pause
import requests
from requests_oauthlib import OAuth1
from selenium import webdriver
from selenium.webdriver import Chrome
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import StaleElementReferenceException

#reddit developer account information/tokens
reddit = praw.Reddit(client_id = '', client_secret = '', user_agent = 'WebScraper')

#twitter developer account information/tokens
oauth = OAuth1('',
  client_secret='',
  resource_owner_key='',
  resource_owner_secret='')

#twitter api urls
mediaUrl = 'https://upload.twitter.com/1.1/media/upload.json'
postUrl = 'https://api.twitter.com/1.1/statuses/update.json'

#location of chrome webdriver used for scraping
webdriver = '/home/tyler/Documents/webscraper/chromedriver'

#takes the top posts from a subreddit and stores in array
titleArray = []
urlArray = []
topPosts = reddit.subreddit('Livestreamfail').top(time_filter='day', limit=10)
driverUrl = Chrome(webdriver)
#loop through array to extract twitch clip url and title of reddit post
for post in topPosts:
    #try catch for exception handling
    try:
        driverUrl.get(post.url)
        #finds video element by common XPATH shared with all videos
        elem = driverUrl.find_element(By.XPATH, '//*[@id="root"]/div/div/div/div[3]/div/div/main/div/div/div[2]/div[1]/div/div[2]/div[2]/div/div/div[1]/div/video')
        videoUrl = elem.get_attribute('src')
        if videoUrl != '':
            #adds title of post and url for later use
            titleArray.append(post.title)
            urlArray.append(videoUrl)           
    #exception handling for deleted clips or posts without clips
    except NoSuchElementException:
        print ('element does not exist')
    except StaleElementReferenceException:
        print ('element does not exist')
driverUrl.close()
#end reddit scraper

dlArray = []
driverDl = Chrome(webdriver)
#loop that opens each url extracted from the reddit scraper
#once the url opens it downloads the video for later use
#additionally stores the file path
for url in urlArray:
    driverDl.get(url)
    pause.seconds(5)
    dlUrl = url.split('twitch.tv/',1)[1]
    dlUrl = dlUrl.replace('%', '_')
    dlUrl = dlUrl.replace('C7', '')
    dl = '/home/tyler/Downloads/' + dlUrl
    dlArray.append(dl)
driverDl.close()

iterator = 0
#loop that uploads each video to twitter
for dl in dlArray:
    #total bytes of file
    videoSize = os.path.getsize(dl)
    #json request headers
    idRequestData = {
        'command': 'INIT',
        'media-type': 'video/mp4',
        'total_bytes': videoSize,
        'media_category': 'tweet_video'
    }
    #INIT 
    #request that returns the media_id for uploading videos
    idRequest = requests.post(url=mediaUrl, data=idRequestData, auth=oauth)
    mediaId = idRequest.json()['media_id']

    #APPEND
    #upload the video to twitter in chunks, the file limit is 15mb which is too small
    bytesCompleted = 0
    segmentIndex = 0
    file = open(dl, 'rb')

    while bytesCompleted < videoSize:
        #reads 4 mb of the file to upload
        chunk = file.read(4 * 1024 * 1024)
        appendRequestData = {
            'command': 'APPEND',
            'media_id': mediaId,
            'segment_index': segmentIndex
        }
        files = {
            'media': chunk
        }

        appendRequest = requests.post(url=mediaUrl, data=appendRequestData, files=files, auth=oauth)        
        #checks status code and is not within the range provided by twitter suspends application
        if appendRequest.status_code < 200 or appendRequest.status_code > 299:
            print(appendRequest.status_code)
            print(appendRequest.text)
            sys.exit(0)
        
        #updates the bytes completed increases the segment index as well
        bytesCompleted = file.tell()
        segmentIndex += 1
        #indicates how much of the file has been uploaded of the full file size
        print("%s / %s" %(bytesCompleted, videoSize))

    #STATUS
    #function that temporarily polls the uploaded video to see if it is done processing
    def checkStatus(processingInfo):
        if processingInfo != None :
            #get the state of upload
            state = processingInfo["state"]
            #get the number of seconds to wait until checking status again
            tts = processingInfo.get("check_after_secs")
            #if upload is not completed the function is called again with new processing info
            if state != 'succeeded':
                time.sleep(tts)
                print ('processing...')
                #get header for status
                statusRequest = {
                    "command": "STATUS",
                    "media_id": mediaId
                }
                #get request that returns the status of upload
                status = requests.get(url=mediaUrl, params=statusRequest, auth=oauth)
                processingInfo = status.json().get('processing_info', None)
                checkStatus(processingInfo)
        else :
            print ('success')

    #function that sends tweet
    def tweet():
        #post header for tweet request
        tweetRequest = {
            "status": titleArray[iterator] + " " + "#twitch",
            "media_ids": mediaId
        }
        req = requests.post(url=postUrl, data=tweetRequest, auth=oauth)
        print(req.json())

    #FINALIZE
    finalizeRequestData = {
        "command": "FINALIZE",
        "media_id": mediaId
    }
    finalizeRequest = requests.post(url=mediaUrl, data=finalizeRequestData,  auth=oauth)    
    processingInfo = finalizeRequest.json().get('processing_info')
    checkStatus(processingInfo)
    tweet()
    iterator += 1

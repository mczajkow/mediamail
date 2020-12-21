import argparse
import jaraco.logging
import logging

log = logging.getLogger(__name__)

class TwitterBot:
    '''
    TwitterBot is a Platform Bot that interacts with Twitter. Twitter supports multiple different query options. In this code, we provide one of three possible types of interaction: (a) Stream on keywords, (b) Stream on geographical locations of interest, (c) Stream on a set of follower IDs to track updates from. This package uses Tweepy to do the interactions with Twitter

    Created on Dec 20, 2020

    @author: Michael
    '''
    
     def __init__(self, configFile):         
         '''
         Initializes the TwitterBot, loading the configuration file. Then starts the query to Twitter.
         '''
    
def get_args():
    '''
    '''
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c",
        "--config",
        dest="config_file",
        default='run/twitterbot.json',
        type=str,
        help="The twitterbot.json configuration file to use",
    )
    jaraco.logging.add_arguments(parser)
    return parser.parse_args()

def main():
    '''
    '''
    options = get_args()
    jaraco.logging.setup(options)
    log.info("Starting Twitterbot")
    TwitterBot tb = TwitterBot()

if __name__ == "__main__":
    '''
    '''
    main()

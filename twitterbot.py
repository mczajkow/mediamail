import argparse
import jaraco.logging
import logging
from utils import ConfigFileHelper

log = logging.getLogger(__name__)

class TwitterBot:
    '''
    TwitterBot is a Platform Bot that interacts with Twitter. Twitter supports multiple different query options. In this code, we provide one of three possible types of interaction: (a) Stream on keywords, (b) Stream on geographical locations of interest, (c) Stream on a set of follower IDs to track updates from. This package uses Tweepy to do the interactions with Twitter
    @author: Michael
    '''
    
    def __init__(self, configFile):         
        '''
         Initializes the TwitterBot, loading the configuration file. Then starts the query to Twitter.
         
        -- configFile string, the location of the configuration JSON used to configure this bot instance. Required, without it an error log is made and nothing happens further
        '''
        if configFile is None:
            log.error("Could not initialize TwitterBot with None config file")
            return
        log.info("Initializing TwitterBot with config file: "+configFile)
        configHelper = ConfigFileHelper(configFile)
        self.conf = configHelper.getConf()
        log.debug(str(self.conf))
    
def get_args():
    '''
    Uses ArgumentParser to pull options off the command line for use by TwitterBot    
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
    Starts a TwitterBot instance given options off the command line using ArgumentParser
    
    @see get_args
    '''
    options = get_args()
    jaraco.logging.setup(options)
    tb = TwitterBot(options.config_file)

if __name__ == "__main__":
    '''
    This is a catch-all so that this file may be used as an entry point from Python, e.g. 'python twitterbot.py'
    '''
    # Merely call main, which then parses arguments and sets up the bot
    main()

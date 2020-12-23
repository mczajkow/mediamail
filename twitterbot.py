import argparse
import jaraco.logging
import logging
from tweepy import OAuthHandler
from tweepy import Stream
from tweepy.streaming import StreamListener
from utils import ConfigFileHelper, TwitterHelper

log = logging.getLogger(__name__)

class TwitterBot(StreamListener):
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
        self.twitterHelper = TwitterHelper(self.conf)
        log.debug(str(self.conf))
        # Set twitter keys/tokens. Check to see they are set first.
        if 'twitter' not in self.conf:
            log.error('No twitter section in configuration. Failing out.')
            return
        if 'consumer_key' not in self.conf['twitter'] or len(str(self.conf['twitter']['consumer_key'])) == 0:
            log.error('Failed to initialize access to twitter. Consumer key provided in configuration is: '+str(self.conf['twitter']['consumer_key']))
            return
        if 'consumer_secret' not in self.conf['twitter'] or len(str(self.conf['twitter']['consumer_secret'])) == 0:
            log.error('Failed to initialize access to twitter. Consumer secret provided in configuration is: '+str(self.conf['twitter']['consumer_secret']))
            return
        if 'access_token' not in self.conf['twitter'] or len(str(self.conf['twitter']['access_token'])) == 0:
            log.error('Failed to initialize access to twitter. Access token provided in configuration is: '+str(self.conf['twitter']['access_token']))
            return
        if 'access_token_secret' not in self.conf['twitter'] or len(str(self.conf['twitter']['access_token_secret'])) == 0:
            log.error('Failed to initialize access to twitter. Access token secret provided in configuration is: '+str(self.conf['twitter']['access_token_secret']))
            return
        self.auth = OAuthHandler(self.conf['twitter']['consumer_key'], self.conf['twitter']['consumer_secret'])
        self.auth.set_access_token(self.conf['twitter']['access_token'], self.conf['twitter']['access_token_secret'])
        # Create instance of the tweepy stream using myself as a listener.
        self.myStream = Stream(auth, listener=self, tweet_mode='extended')
        # Set up the queries based on what is put in the queries section of the configuration. Check to see if it is set.
        if 'queries' not in self.conf:
            log.error('No queries section in configuration. Failing out, don\'t know what to query for on Twitter')
            return
        if 'aois' in self.conf['queries']:
            log.info('Setting up an aoi query to Twitter')
            # For it to be valid it has to have at least one bounding box, e.g. length >= 4
        elif 'followers' in self.conf['queries']:
            log.info('Setting up a follower query to Twitter')
        elif 'tracks' in self.conf['queries']:
            log.info('Setting up a tracks query to Twitter')
        
            
     def on_data(self, data):
        """        
        Processes a new Twitter message, convert it to TwJSON and send it to IRCBot.
        
        -- data is a JSON string that comes in from Twitter.
        """
    
    def on_error(self, status):
        """
        Processes error messages in the Handler.
        
        -- status is a string error message.
        """
    
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

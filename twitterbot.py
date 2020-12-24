import argparse
import jaraco.logging
import json
import logging
from tweepy import OAuthHandler
from tweepy import Stream
from tweepy.streaming import StreamListener
from tweepy.utils import parse_datetime
from textblob import TextBlob
from utils import ConfigFileHelper, TwitterHelper, ElasticSearchHelper

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
        log.info("Initializing TwitterBot with config file: " + configFile)
        configHelper = ConfigFileHelper(configFile)
        self.conf = configHelper.getConf()
        self.twitterHelper = TwitterHelper(self.conf)
        log.debug(str(self.conf))
        # Elastic Search: setup
        if 'elastic' not in self.conf:
            # No elastic search means nothing we can insert data into. Fail out.
            log.error('No elastic section in configuration. Failing out.')
            return
        if 'host' not in self.conf['elastic']:
            # No host, also fail out.
            log.error('No host configured in elastic section of configuration. Failing out.')
            return
        if 'port' not in self.conf['elastic']:
            # No port, also fail out.
            log.error('No port configured in elastic section of configuration. Failing out.')
            return
        if 'index' not in self.conf['elastic']:
            # No host, also fail out.
            log.error('No index configured in elastic section of configuration. Failing out.')
            return
        log.debug('Setting up Elastic Search...')
        self.elasticSearchHelper = ElasticSearchHelper(self.conf['elastic']['host'], self.conf['elastic']['port'], self.conf['elastic']['index'])
        log.info('Elastic Search setup complete.')
        # Twitter: Set twitter keys/tokens. Check to see they are set first.
        if 'twitter' not in self.conf:
            log.error('No twitter section in configuration. Failing out.')
            return
        if 'consumer_key' not in self.conf['twitter'] or len(str(self.conf['twitter']['consumer_key'])) == 0:
            log.error('Failed to initialize access to twitter. Consumer key provided in configuration is: ' + str(self.conf['twitter']['consumer_key']))
            return
        if 'consumer_secret' not in self.conf['twitter'] or len(str(self.conf['twitter']['consumer_secret'])) == 0:
            log.error('Failed to initialize access to twitter. Consumer secret provided in configuration is: ' + str(self.conf['twitter']['consumer_secret']))
            return
        if 'access_token' not in self.conf['twitter'] or len(str(self.conf['twitter']['access_token'])) == 0:
            log.error('Failed to initialize access to twitter. Access token provided in configuration is: ' + str(self.conf['twitter']['access_token']))
            return
        if 'access_token_secret' not in self.conf['twitter'] or len(str(self.conf['twitter']['access_token_secret'])) == 0:
            log.error('Failed to initialize access to twitter. Access token secret provided in configuration is: ' + str(self.conf['twitter']['access_token_secret']))
            return
        self.auth = OAuthHandler(self.conf['twitter']['consumer_key'], self.conf['twitter']['consumer_secret'])
        self.auth.set_access_token(self.conf['twitter']['access_token'], self.conf['twitter']['access_token_secret'])
        # Create instance of the tweepy stream using myself as a listener.
        self.myStream = Stream(self.auth, listener=self, tweet_mode='extended')
        # Set up the queries based on what is put in the queries section of the configuration. Check to see if it is set.
        if 'queries' not in self.conf:
            log.error('No queries section in configuration. Failing out, don\'t know what to query for on Twitter')
            return
        if 'aois' in self.conf['queries']:
            log.info('Setting up an aoi query to Twitter')
            # For it to be valid it has to have at least one bounding box, e.g. length >= 4 and the length should be modulo 4 = 0.
            locations = self.conf['queries']['aois']
            if len(locations) % 4 != 0:
                log.error('The configured aois to query for Twitter are not valid. The list should contain quadruplets of floating values. Instead, it has partial bounding boxes in it. See DESIGN.md for more information. No query to Twitter is made.')
                return
            elif len(locations) == 0:
                log.error('The configured aois to query for Twitter are not valid. The list should contain quadruplets of floating values. Instead, it has nothing in it. See DESIGN.md for more information. No query to Twitter is made.')
                return
            # Each of these has to be made into a string for Twitter to process it via Tweepy.
            stringLocations = []
            for floatLocation in locations:
                stringLoations += str(floatLoation)
            log.debug('Calling filter on Twitter with locations: ' + str(stringLocations))
            self.myStream.filter(locations=stringLocations, is_async=True)
            log.info('Filter set! Twitter is now scanning these aois.')
        elif 'followers' in self.conf['queries']:
            log.info('Setting up a follower query to Twitter')
            # We have to have at least one follower integer ID in there for this to work.
            followers = self.conf['queries']['followers']
            if len(followers) == 0:
                log.error('The configured followers list to query is empty. It needs to have at least one Twitter ID. See DESIGN.md. No query to Twitter is made')
                return
            # Each of these needs to be made into a string for Twitter to process it via Tweepy
            stringFollowers = []
            for intFollower in followers:
                stringFollowers += [str(intFollower)]
            log.debug('Calling filter on Twitter with followers: ' + str(stringFollowers))
            self.myStream.filter(follow=stringFollowers, is_async=True)
            log.info('Filter set! Twitter is now scanning these followers.')
        elif 'tracks' in self.conf['queries']:
            log.info('Setting up a tracks query to Twitter')
            tracks = self.conf['queries']['tracks']
            # We have to have at least one track in there for this to work.
            if len(tracks) == 0:
                log.error('The configured tracks list to query is empty. It needs to have at least one key word. See DESIGN.md. No query to Twitter is made')
                return
            log.debug('Calling filter on Twitter with tracks: ' + str(tracks))            
            self.myStream.filter(track=tracks, is_async=True)
            log.info('Filter set! Twitter is now scanning these tracks.')
        # Set up an error counter to track consecutive errors
        self.twitterErrorCounter = 0
            
    def on_data(self, data):
        '''        
        Processes a new Twitter message and then stores it in Elastic Search using the ElasticSearchHelper

        -- data unknown Tweepy type, data that comes in from Twitter. Required, if None a warning will be logged and nothing else will happen.
        @see utils.ElasticSearchHelper
        '''        
        if data is None:
            log.warning('Incoming data from Twitter was None. Ignoring')
            return
        # Parse the data into a JSON dictionary
        tweetData = {}
        try:
            tweetData = json.loads(data)
        except Exception as e:
            log.warning('Failed to load the tweet JSON into a dictionary: ' + str(e))
            return
        # Pull out the text.
        tweetText = self.twitterHelper.getTweetText(tweetData)
        # This could be None, check.
        if tweetText is None:
            # It would be difficult to process a tweet with no text, so ignore that too.
            log.warning('Incoming data from Twitter had no text in the tweet. Ignoring')
            return
        log.debug('Incoming tweet, text: ' + str(tweetText))        
        # Reset the self.twitterErrorCounter to zero. We have something that is good.
        self.twitterErrorCounter = 0
        # Check black and white listed words in the text, in that order.
        if 'filters' in self.conf and 'blacklist_words' in self.conf['filters']:
            for word in self.conf['filters']['blacklist_words']:
                if str(word).lower() in str(tweetText).lower():
                    # Blacklisted. Ignore it.
                    log.debug('Tweet contained blacklisted word: ' + str(word) + '. Ignoring.')
                    return
        if 'filters' in self.conf and 'whitelist_words' in self.conf['filters']:
            for word in self.conf['filters']['whitelist_words']:
                if str(word).lower() not in str(tweetText).lower():
                    # Whitelisted. Ignore it.
                    log.debug('Tweet did not contain whitelisted word: ' + str(word) + '. Ignoring.')
                    return
        # Next we pull out of the tweet data all the things needed to put into Elastic Search
        authorName = None
        authorLocation = None
        screenName = None
        if 'user' in tweetData:
            if 'name' in tweetData['user']:
                authorName = tweetData['user']['name']
            if 'screen_name' in tweetData['user']:
                screenName = tweetData['user']['screen_name']
            if 'location' in tweetData['user']:
                authorLocation = tweetData['user']['location']
        createdAt = None
        if 'created_at' in tweetData:
            createdAt = parse_datetime(tweetData["created_at"])
         # To get tokens, hashtags, etc. we need to tokenize the text, and eliminate common words and short words.
        spaceSplit = tweetText.lower().split(" ")
        tokens = []
        references = []
        hashtags = []
        for token in spaceSplit:
            if "'" in token:
                continue
            # Now eliminate configured common words.
            if 'filters' in self.conf and 'common_words' in self.conf['filters']:
                if token in self.conf['filters']['common_words']:
                    continue
            # Now check for size greater than three
            if len(token) > 3:
                # Its a keeper but we are going to strip @ and # for tokens
                if token.startswith("@"):
                    references += [token]  # Keep this as a reference and include the @ mark.
                    token = token[1:]
                if token.startswith("#"):
                    hashtags += [token]  # Keep this as a hashtag and include the # mark.
                    token = token[1:]
                tokens += [token]
        # Location
        location = None
        if 'geo' in tweetData and tweetData['geo'] is not None:
            location = str(tweetData['geo']['coordinates'][0]) + ',' + str(tweetData['geo']['coordinates'][1])
        # Locality Confidence
        locality = self.twitterHelper.localityCheckOfATweet(tweetData)
        # Confidence is 0.0 (false) or 1.0, for now
        # TODO: Revisit other values later, such as if the tweet originates near the configured location, perhaps that is local?
        localityConfidence = 0.0
        if locality is True:
            localityConfidence = 1.0
        # Place, place name
        placeName = None
        placeFullName = None
        if 'place' in tweetData and tweetData['place'] is not None:
            if 'full_name' in tweetData['place']:
                placeFullName = tweetData['place']['full_name']
            if 'name' in tweetData['place']:
                placeName = tweetData['place']['name']
        # Polarity, Subjectivity, Sentiment
        textB = TextBlob(tweetText)  # TextBlob contains an assessment capability.
        sentiment = None
        # determine if sentiment is positive, negative, or neutral
        if textB.sentiment.polarity < 0:
            sentiment = 'negative'
        elif textB.sentiment.polarity == 0:
            sentiment = 'neutral'
        else:
            sentiment = 'positive'
        log.debug('Inserting fully parsed Tweet into Elastic Search')
        self.elasticSearchHelper.storeData(authorName, authorLocation, screenName, createdAt, hashtags, localityConfidence, location, placeName, placeFullName, textB.sentiment.polarity, references, 'twitter', sentiment, textB.sentiment.subjectivity, tweetText, tokens)
        log.debug('Elastic Search update complete.')
                                
    def on_error(self, status):
        '''
        Processes error messages that come from Twitter via the use of the query.
        
        -- status unknown type, this is an error message. Required, if None nothing will happen.
        '''
        if status is None:
            return
        log.debug('Incoming error from the Twitter query issued: ' + str(status))
        if self.twitterErrorCounter >= 3:
            # Log this at error if we're getting a lot of consecutive errors
            log.error('Receiving consistent errors from Twitter. Suggest restarting. Error is: ' + str(status))
        else:
            self.twitterErrorCounter += 1

    
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

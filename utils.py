import base62
import elasticsearch.helpers
import logging
import json
import tweepy
import time
from elasticsearch import Elasticsearch
from tweepy import OAuthHandler

log = logging.getLogger(__name__)


class ConfigFileHelper:
    '''
    ConfigFileHelper loads JSON configuration files and then holds on to a reference to them in memory as a dictionary of terms.
    @author: Michael
    '''
    
    def __init__(self, configFile):
        '''
        Initializes the class and loads in configuration details from the file. First looks into the folder where configFile is and if a global.json is there, loads that into memory. Then proceeds to load configurationFile and overwrites any property that is found in global.json.
                
        -- configFile string, the location of the JSON config file to load. Required, without it nothing is loaded and an empty internal dictionary is set up. An error is logged in that case and the global conf variable will remain empty.
        '''
        log.debug('Attempting to load configFile: ' + configFile + ' and any global.json found in that folder.')
        self.conf = {}
        if configFile is None:
            log.error('Failed to load configuration file, None was passed in as a parameter to ConfigFileHelper. An empty configuration dictionary will result.')
            return
        parts = configFile.split('/')
        globalJsonFile = '/'.join(parts[:len(parts) - 1]) + '/global.json'
        try:
            with open(globalJsonFile) as f:
                data = json.load(f)
                for key in data:
                    self.conf[key] = data[key]
            log.debug('Loaded global.json file found at: ' + globalJsonFile)
        except Exception as e:
            # Failed to load global.json. It may not exist, or other problem.
            log.warning('Failed to load: ' + globalJsonFile + '. Proceeding to load configFile on itself. Exception is: ' + str(e))
        # And now load configFile on top of this.
        try:
            with open(configFile) as f:
                data = json.load(f)
                for key in data:
                    self.conf[key] = data[key]
        except Exception as e:
            log.error('Failed to load: ' + configFile + ". This will result in an empty configuration. Exception is: " + str(e))
        log.info('Loaded configuration file: ' + configFile + ' successfully.')
        
    def getConf(self):
        '''
        Returns the global configuration dictionary stored in memory in this class instance.
        
        @return dictionary, the configuration loaded by this file. May be empty, but is never None
        '''
        return self.conf


class ElasticSearchHelper:
    '''
    ElasticSearchHelper provides functions to access and store data to Elastic Search for any bot to use.
    @author: Michael
    '''

    def __init__(self, elasticSearchHost, elasticSearchPort, elasticSearchIndex, conf):
        '''
        Initializes the ElasticSearchhelper class instance
        
        -- elasticSearchHost string, the host name where to find Elastic Search. Required, if not given, an error will be issued and the class will not set up a connection.
        -- elasticSearchPort integer, the port to connect to Elastic Search with. Required, if not given, an error will be issued and the class will not set up a connection.
        -- elasticSearchIndex string, the name of the index to send data and queries to. Required, if not given, an error will be issued and the class will not set up a connection.
        -- conf dictionary, the configuration of the bot, as loaded in the ConfigFileHelper.
        @see ConfigFileHelper
        '''
        if elasticSearchHost is None:
            log.error('Could not initialize Elastic Search with a None host name given.')
            return
        if elasticSearchPort is None:
            log.error('Could not initialize Elastic Search with a None port given.')
            return
        if elasticSearchIndex is None:
            log.error('Could not initialize Elastic Search because the index supplied is None.')
            return
        try:
            self.elasticSearch = Elasticsearch(['http://' + elasticSearchHost + ':' + str(elasticSearchPort)])
        except Exception as e:
            log.error('Failed to initialize connection to Elastic Search: ' + str(e))
        self.elasticSearchIndex = elasticSearchIndex
        # This class also needs access to an instance of MMIDHelper.
        self.mmidHelper = MMIDHelper(conf)
             
    def parseQueryResults(self, queryResults, mmid=None):
        '''
        The contents of a query in Elastic Search have a lot of extra Elastic Search metadata in them. This method will pull out the record(s) stored as-is and return them in a list.
        
        -- queryResults dictionary, the results of the query containing the elastic search metadata. Required to not be None.
        -- mmid string, by specifying an mmid an exact match will be checked on the records prior to returning them. Only matches with this mmid will be returned.
        @return a list of dictionary, these are the original record formats put in via storeData, @see storeData
        '''
        workingResultsReturned = []
        if queryResults is None or isinstance(queryResults, dict) is False:
            log.debug('Input queryResults is None or not a dictionary. Returning an empty list.')
            return workingResultsReturned
        # Content is in { "hits" : { "hits" : [ { "_source" : {HERE} } ... ] } }
        if 'hits' not in queryResults or isinstance(queryResults['hits'], dict) is False:
            log.debug('Unrecognizes query results, expecting hits to be in top level: ' + str(queryResults))
            return workingResultsReturned
        innerHits = queryResults['hits']
        if 'hits' not in innerHits or isinstance(innerHits['hits'], list) is False:
            log.debug('Unrecognizes query results, expecting hits to be in {"hits":{}}: ' + str(queryResults))
            return workingResultsReturned
        # Each item in the results also needs to be cleaned up.
        for esRecord in innerHits['hits']:
            if isinstance(esRecord, dict) is False:
                log.debug('Inner hits are not dictionaries, skipping.')
                continue
            if '_source' not in esRecord:
                log.debug('The field _source is not specified in the list item of an inner hit. Skipping')
                continue
            source = esRecord['_source']
            # This should be a dictionary.
            if isinstance(source, dict) is False:
                log.debug('The _source of an Elastic Search hit is not a dictionary? skipping.')
                continue
            workingResultsReturned += [source]
        # Additional checks.
        resultsReturned = []
        for result in workingResultsReturned:
            # TODO #20-Create-Elastic-Search-Indecies-with-Mappings: If this is done, a mapping can be made to eliminate the need to do extra work here for mmid matchin as that can be put into the query.
            if mmid is not None and 'mmid' in result:
                # Check match
                if result['mmid'] == mmid:
                    resultsReturned += [result]  # Match found.
                else:
                    # Skip, we don't want this one.
                    continue
            # If there are no additional filters to try out, keep it.
            resultsReturned += [result]
        # Return results.
        return resultsReturned
            
    def query(self, queryDict):
        '''
        Queries Elastic Search with a single query and returns the results of the query.
        
        -- queryDict dictionary. Elastic Search uses dictionaries with "query" in them to return results. Required. Without this being set, a WARNING log is issued and nothing happens.
        @return dictionary result of issuing the query
        '''
        if queryDict is None:
            log.warning('Could not query Elastic Search with None query dictionary.')
            return
        try:
           return self.elasticSearch.search(index=self.elasticSearchIndex, body=queryDict)
        except Exception as e:
            log.error('Failed query to Elastic Search for this query: ' + str(queryDict) + " Error is: " + str(e))
        
    def scan(self, queryDict):
        '''
        Queries Elastic Search with a single query and returns the results of the query.
        
        -- queryDict dictionary. Elastic Search uses dictionaries with "query" in them to return results. Required. Without this being set, a WARNING log is issued and nothing happens.
        @return iterator this can be used to scan over a list of results all in JSON string format.
        '''
        if queryDict is None:
            log.warning('Could not query Elastic Search with None query dictionary.')
            return
        try:
            return elasticsearch.helpers.scan(self.elasticSearch, index=self.elasticSearchIndex, query=queryDict)
        except Exception as e:
            log.error('Failed query to Elastic Search for this query: ' + str(queryDict) + " Error is: " + str(e))
        
    def storeData(self, author=None, authorLocation=None, authorScreenName='Unknown', createdAt=None, hashtags=[], location=None, localityConfidence=0.0, placeName=None, placeFullName=None, polarity=None, references=[], source=None, sentiment=None, subjectivity=None, text=None, tokens=[], url=None):
        '''
        Stores data given into ElasticSearch.
        
        -- author string, the name of the author. Optional, not required to be put into the index.
        -- authorLocation string, the location of the author. Optional, not required to put into the index.
        -- authorScreenName string, the social media handle or screen name. Optional, if not provided then 'Unknown' is used.
        -- createdAt string, the date and time the tweet was made in ISO 8601 format. Required, without it we can't really query it back. If not provided then a DEBUG log will be made and nothing done. ISO 8601 formatting is not enforced by this method. Providing anything else would cause the message to be indexed but never found in a time based query.
        -- hashtags list of string, the hashtags used within the body of the message (e.g. #fun). Optional, if not provided then an empty list is indexed.
        -- location string, in the format of Lat,Lon where Lat and Lon are floats in degrees. Optional, if not provided then nothing is put in the index.
        -- locatlityConfidence float, a number from 0.0 to 1.0 indicating the confidence on how local to the configured location this author is physically. Required, default is 0.0. If a non-number or out of range number is provided, then a DEBUG log will be made and nothing done.
        -- placeName string, the name of the place the author of the message is. Optional, not required to be put into the index.
        -- placeFullName string, the full unabbreviated place name the author of the message is. Optional not required to be put into the index.
        -- polatity float, a number -1.0 to 1.0. @see https://en.wikipedia.org/wiki/Sentiment_analysis. Optional, not required to be put in the index. If provided, it must be a float type and within the range. If not, it will not be put into the index.
        -- references list of string, a list of references made within the text (e.g. @johndoe). Optional, if not provided then an empty list is indexed.
        -- sentiment string, @see https://en.wikipedia.org/wiki/Sentiment_analysis. Should be one of ['negative','neutral','positive']. Optional, not required to be put into the index.
        -- source string, the name of the social media platform storing data. Optional, not required to be put into the index.
        -- subjectivity float, a number -1.0 to 1.0. @see https://en.wikipedia.org/wiki/Sentiment_analysis. Optional, not required to be put into the index. If provided, it must be a float type within the range. If not, it will not be put into the index.
        -- text string, the body of the message being indexed. Required, without it there is no data. If not provided, then a DEBUG log will be made and nothing done.
        -- tokens list of string, the text of the message broken down into single words for token matching purposes. Optional, if not provided then an empty list is indexed.
        -- url string, the URL directly to the message on the media platform. Optional. If not supplied, nothing will be put in the index.
        '''
        body = {}
        # Check each field for None and then do the appropriate actions.
        if author is not None:
            body['author'] = author
        if authorLocation is not None:
            body['author_location'] = authorLocation
        if authorScreenName is not None:
            body['author_screen_name'] = authorScreenName
        if createdAt is not None:
            body['created_at'] = createdAt
        else:
            log.debug('Provided data to store has None createdAt. Ignoring.')
            return
        if hashtags is not None and isinstance(hashtags, list):
            body['hashtags'] = hashtags
        if location is not None:
            body['location'] = location
        if localityConfidence is not None:
            lC = 0.0
            try:
                lC = float(locatlityConfidence)
            except:
                # Not a number.
                log.debug('Provided data has a locality confidence that is not a float. Ignoring.')
                return
            if lC < 0.0 or lc > 1.0:
                log.debug('Provided data has a locality confidence that is not between 0.0 and 1.0 inclusive. Ignoring.')
                return
            body['locality_confidence'] = lC
        else:
            body['locality_confidence'] = 0.0  # Default is zero.
        if placeName is not None:
            body['place_name'] = placeName
        if placeFullName is not None:
            body['place_full_name'] = placeFullName
        if polarity is not None:
            pol = 0.0
            try:
                pol = float(polarity)
                if pol >= -1.0 or pol <= 1.0:
                    body['polarity'] = pol
                # If not in the range, don't set polarity
            except:
                # Not a number. Just don't set polarity
                pass
        if references is not None and isinstance(references, list):
            body['references'] = references
        if sentiment is not None:
            if sentiment == 'neutral' or sentiment == 'positive' or sentiment == 'negative':
                body['sentiment'] = sentiment
        if source is not None:
            body['source'] = source
        if subjectivity is not None:
            sub = 0.0
            try:
                sub = float(subjectivity)
                if sub >= -1.0 or sub <= 1.0:
                    body['subjectivity'] = sub
                # If not in the range, don't set polarity
            except:
                # Not a number. Just don't set polarity
                pass
        if text is not None:
            body['text'] = text
        else:
            log.debug('Provided data to store has None text. Ignoring.')
            return
        if tokens is not None and isinstance(tokens, list):
            body['tokens'] = tokens
        if url is not None:
            body['url'] = url
        # Generate a unique ID.
        # TODO #21-Move-MMID-Generation-out-of-ElasticSearchHelper: This next line seems like it should not be in this class. It makes a cleaner design to pass this in. It makes ElasticSearchHelper no longer need a MMIDHelper and the oddity of the constructor requiring the entire configuration after only requiring a sub-set. Remove this here and put it in the calling class.
        body['mmid'] = self.mmidHelper.generateID()
        # wait 0.01 to the next record, to ensure it would have a unique mmid.
        time.sleep(0.01)
        log.debug('Inserting into Elastic Search this body: ' + str(body))
        try:
            self.elasticSearch.index(index=self.elasticSearchIndex,
                     doc_type="test-type",
                     body=body)
        except Exception as e:
            log.error("Could not index in Elastic Search: " + str(e))



class MMIDHelper:
    '''
    MMIDHelper provides functions to generate, check, and manage MMIDs (media mail IDs)
    @author: Michael
    '''
    
    def __init__(self, config):
        '''
        Sets up the MMIDHelper using the configuration loaded from a file
        
        -- config dictionary, the loaded properties from the configuration files for the bot. Required, if None then an error is logged and nothing happens.
        @see ConfigFileHelper
        '''
        if config is None:
            log.error('Failed to initialize MMIDHelper as provided config dictionary is None. MMIDHelper is not set up properly.')
            return
        self.conf = config
    
    def generateID(self):
        '''
        Media Mail needs an ID associated with each record to be put into the Elastic Search record store and used later for looking up records. IDs are 5 alpha-numeric characters based on wall time.
        
         @return string, 5 characters long [A-Za-z0-9] unique to the 1/100th of a second.
        '''
        # The code generated is based on the hundreths of second past epoch
        timeNow = int(time.time() * 100)
        # We use a reference number (62^5-1) to generate five 62-digit characters
        totalCodes = (62 * 62 * 62 * 62 * 62) - 1
        # timeNow % totalCodes gives us a unique number for this 1/100th of 1 second.
        # this is unique for 916132832 1/100ths of a second or about 3.5 months.
        code = timeNow % totalCodes
        code62 = base62.encode(code).zfill(5)
        return code62
    
    def isBlacklisted(self, mmid):
        '''
        The configuration of Media Mail allows for a black list of MMIDs, special cases which should not be used. This function checks that list for the given MMID.
        
        -- mmid string, 5 characters long [A-Za-z0-9]. If None is given, False will be returned and an error reported on the DEBUG log.
        @return boolean, True if on the blacklist, False otherwise
        '''
        if mmid is None:
            log.debug('Can not check blacklist of tokens if given a None MMID. False returned')
            return False
        if 'tokens' not in self.conf:
            # No token configuration. Can't check blacklist.
            log.debug('Could not check blacklist as no token section in configuration is set up.')
            return False
        if 'blacklist' not in self.conf['tokens']:
            # No blacklist configuration. Can't check blacklist.
            log.debug('Could not check blacklist as no blacklist section in the tokens in the configuration was set up.')
            return False
        if isinstance(self.conf['tokens']['blacklist'], list):
            # Now check contents.
            if mmid in self.conf['tokens']['blacklist']:
                return True
        else:
            log.debug('The configuration of the blacklist tokens in the configuration is not a list. Any check for blacklist tokens will be False.')
        # All other cases, just return False.
        return False


class TwitterHelper:
    '''
    This class performs common Twitter functions needed by bots that interact with this social media platform.
    @author: Michael
    '''

    def __init__(self, config):
        '''
        Sets up the TwitterHelper using the configuration loaded from a file
        
        -- config dictionary, the loaded properties from the configuration files for the bot. Required, if None then an error is logged and nothing happens.
        @see ConfigFileHelper
        '''
        if config is None:
            log.error('Failed to initialize TwitterHelper as provided config dictionary is None. TwitterHelper is not set up properly.')
            return
        self.conf = config
         # Now look up the consumer_key, consumer_secret, access_token, access_token_secret in config.
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
        # Set up an OAuthHandler for the helper class to use.
        log.debug('Setting up the self auth OAuthHandler for the helper class.')
        self.auth = OAuthHandler(self.conf['twitter']['consumer_key'], self.conf['twitter']['consumer_secret'])
        self.auth.set_access_token(self.conf['twitter']['access_token'], self.conf['twitter']['access_token_secret'])
        log.debug('Done!')
    
    def favorite(self, idoftweet):
        '''
        This methond will take the tweet ID and then favorite it.
        
        -- idoftweet string or integer, representing the tweet's ID. If None is given, nothing happens other than a warning log.
        '''
        log.debug('Attempting to like a tweet.')
        if idoftweet is None:
            log.warning('The ID of the tweet to favorite was None. Ignoring.')
            return
        # Make API call
        log.debug('Setting up API for the call')
        api = tweepy.API(self.auth)
        reply = ""
        log.debug("Liking this tweet: " + str(idoftweet))
        try:
            reply = api.create_favorite(id=int(idoftweet))
            log.debug("Tweet liked")
        except Exception as e:
            log.warning("Error in liking the tweet: " + str(e) + " with reply: " + str(reply))
        
    def getTweetText(self, tweetData):
        '''
        Looks at the content of incoming tweet data and pulls out the raw text found within.
        
        -- tweetData dictionary, of parsed Tweet JSON. Required, if None is passed then None is returned. If it is bad JSON, an error is thrown and None is returned.
        @return string, the raw full tweet text contained therein. None is returned tweetData has bad/unexpected content or there really is no tweet raw text in it.
        '''
        if tweetData is None:
            log.debug('Tweet contains no text within it, as the tweetData given was None.')
            return None
        if "extended_tweet" in tweetData:
            # Special class of Tweets have their data in this location. Check here first.
           return tweetData['extended_tweet']['full_text']
        elif 'retweeted_status' in tweetData:
            # Retweets have their text data somewhere else.
            if 'extended_tweet' in tweetData['retweeted_status'] and 'full_text' in tweetData['retweeted_status']['extended_tweet']:
                return tweetData['retweeted_status']['extended_tweet']['full_text']
        # Otherwise, try just 'text' at the top level.
        try:
            return tweetData['text']
        except Exception as e:
            # Some kind of error in getting the data.
            log.warning('Failed to find the text in the tweet because of an error: ' + str(e))
            return None
        log.info('Tweet contains no text that could be found.')
        return None
    
    def localityCheckOfATweet(self, tweetData):
        """
        Each tweet has several places where the name of the tweeter's town can be hidden. This function pulls them out and then uses @see localityCheckOfAPlace to see if the person is local.
                
        -- tweetData dictionary, the parsed JSON of a Tweet. Required. Without it, nothing can be determined and after a DEBUG log, False is returned.
        @return boolean, True if the tweet is from a local person, False otherwise.
        """
        if tweetData is None:
            log.debug('Tweet contains no place information in it as the tweetData given was None.')
            return False
        town1 = None
        town2 = None
        town3 = None
        log.debug(str(tweetData))
        if 'place' in tweetData and tweetData['place'] is not None:
            if 'full_name' in tweetData['place']:
                town1 = tweetData['place']['full_name']
            if 'name' in tweetData['place']:
                town2 = tweetData['place']['name']
        elif 'user' in tweetData:
            if 'location' in tweetData['user']:
                town3 = tweetData['user']['location']
        if self.localityCheckOfAPlace(town1) or self.localityCheckOfAPlace(town2) or self.localityCheckOfAPlace(town3):
            return True
        return False
                
    def localityCheckOfAPlace(self, placeFullName):
        """
        Each tweet has a locality place name in it. This function will look at the configuration to see if a given place is from someone who lives near. If so, it returns True, False otherwise.
        
        -- placeFullName string, a place name of the tweet sender. Required. Without it, nothing can be determined and after a DEBUG log, False is returned.
        @return boolean, True if the tweet is from a loccal person, False otherwise.
        """
        if placeFullName is None:
            log.debug('The placeFullName given was None. Returning False.')
            return False
        # Pull out the various parts of the configuration needed
        if 'locality' not in self.conf:
            # No locality set in the configuration. Nothing can ever be True now, so return False.
            return False
        local_towns = []
        state_abbreviation = ""
        state_full = ""
        if 'local_towns' in self.conf['locality']:
            local_towns = self.conf['locality']['local_towns']
        if 'state_abbreviation' in self.conf['locality']:
            state_abbreviation = self.conf['locality']['state_abbreviation']
        if 'state_full' in self.conf['locality']:
            state_full = self.conf['locality']['state_full']        
        # Locality Check assumes False first.
        try:
            # Could be the name of the town after taking out a comma, e.g. "Berlin, NJ"
            town = placeFullName.split(",")
            if town[0] in local_towns and state_abbreviation in town[1]:
                return True
        except Exception as e:
            # Some problem. OK keep going.
            pass
        try:
            # Relax the constraint a little and ignore case.
            town = placeFullName.split(",")
            if state_full.lower() in town[1].lower() or state_abbreviation.lower() in town[1].lower():
                # This is in the local state. Check town.
                for interestedTown in local_towns:
                    if town[0].lower() in interestedTown.lower():
                        return True
        except Exception as e:
            # Some problem. OK keep going.
            pass
        # Maybe the name has no comma in it? That's OK too.
        try:
            if state_abbreviation.lower() in placeFullName.lower() or state_full.lower() in placeFullName.lower():
                # This is in the local state. Check town.
                for interestedTown in local_towns:
                    if interestedTown.lower() in placeFullName.lower():
                        return True
        except Exception as e:
            # Some problem. OK keep going.
            pass
        # No more places it could be...                           
        return False

    def reply(self, idoftweet, prose, tweetOwner):
        '''
        This method takes a tweet ID, prose, and the original tweetOwner and issues a status_update (Tweet) to reply to the original owner by prepending their name to the prose, e.g. @tweetOwner
        
        -- idoftweet a string or integer, representing the tweet's ID. If None or empty is given then nothing happens other than a warning log.
        -- prose the message, must be less than 281 characters sans the name of the tweetOwner, will be rejected if not. Required. If None or empty is given, nothing happens other than a warning log.
        -- tweetOwner the screen name of the owner, without the @. Required. If None or empty is given, nothing happens other than a warning log.
        '''
        if idoftweet is None or len(idoftweet) == 0:
            log.warn('Could not reply to the tweet ID given as it was None or empty')
            return
        if prose is None or len(prose) == 0:
            log.warn('Could not reply to the tweet ID given as the prose was None or empty')
            return
        if tweetOwner is None or len(tweetOwner) == 0:
            log.warn('Could not reply to the tweet ID given as the tweetOwner was None or empty')
            return
        # Make API call
        api = tweepy.API(self.auth)        
        assembledMessage = '@' + tweetOwner + ' ' + prose
        # Tweets can not be more than 280 characters. Check and if that exceeds, print out a WARN.
        if len(assembledMessage) > 280:
            log.warn('Tweet reply exceeds length of 280 characters. Ignoring this reply: ' + assembledMessage)
            return
        reply = ''
        log.debug('Replying to this tweet: ' + str(idoftweet) + ' with tweet: ' + assembledMessage)
        try:
            reply = api.update_status(assembledMessage, in_reply_to_status_id=int(idoftweet))
            log.debug('Tweet sent!')
        except Exception as e:
            log.warning('Error in replying to the tweet: ' + str(e) + ' with reply: ' + str(reply))

            
class ScoringHelper:
    '''
    This class is used to help score data found in Elastic Search according to user preferences found in the configuration.    
    @author: Michael
    '''
    
    def __init__(self, config):
        '''
        Sets up the ScoringHelper using the configuration loaded from a file
        
        -- config dictionary, the loaded properties from the configuration files for the bot. Required, if None then an error is logged and nothing happens.
        @see ConfigFileHelper
        '''
        self.conf = {}
        if config is None:
            log.error('Failed to initialize ScoringHelper as provided config dictionary is None. ScoringHelper is not set up properly.')
            return
        if isinstance(config, dict) is False:
            log.error('Configuration passed into ScoringHelper is not a dictionary. ScoringHelper is not set up properly.')
            return
        self.conf = config
        
    def scoreContent(self, record):
        '''
        Takes data stored in Elastic Search and then assigns priority to it based on the content and what is in the configuration.

        -- record dictionary, a record found in Elastic Search. Required. If none, the default zero score is returned and a warning issued.        
        @return integer, the score for that query data based on configuration. Scores can be any number including negatives.
        @see DESIGN.md
        @see ElasticSearchHelper
        '''
        if record is None:
            log.warning('Could not score data as None was passed in. Zero being returned')
            return 0
        if isinstance(record, dict) is False:
            log.warning('Data passed into scoreContent is not a dictionary. Zero being returned')
            return 0
        # Similarly we need the section 'scoring' to be there too
        if 'scoring' not in self.conf:
            log.warning('There is no scoring section in the configuration. Returning 0.')
            return 0
        score = 0  # start off at zero
        # LENGTH - score points based on how many tokens arein the record.
        if 'points_per_word' in self.conf['scoring']:
            ppw = 0
            try:
                ppw = int(self.conf['scoring']['points_per_word'])
            except Exception as e:
                # Not an integer?
                log.debug('Could not utilize points_per_word in the scoring section of the configuration: ' + str(e))
            if 'text' in record:
                score += (len(record['text'].split(' ')) * ppw)
            else:
                log.debug('Data record from Elastic Search had no text in it. No length based scoring was done.')
        # LOCALITY
        # TODO #6-Move-Locality-to-Mailbot. This should not come directly from the record but rather be determined here in this method with the record data.
        # Note: decided not to put a partial implementation of this in and will circle back to handle this later.
        if 'locality_multiplier' in self.conf['scoring']:
            lm = 0
            try:
                lm = int(self.conf['scoring']['locality_multiplier'])
            except Exception as e:
                # Not an integer?
                log.debug('Could not utilize locality_multiplier in the scoring section of the configuration: ' + str(e))
            if 'locality_confidence' in record:
                score += float(lm) * record['locality_confidence']
        # TODO #7-Redesign-Follower-Scoring: Twitterchat had this capability but Mediamail has to implement this differently. It would need to be the follower of the user who gets the e-mail.
        # KEYWORDS of INTEREST
        if 'interested_words' in self.conf['scoring']:
            # Parse each one, provided a dictionary was given.
            if isinstance(self.conf['scoring']['interested_words'], dict) is False:
                log.debug('Could not score keywords of interest, the value provided in the configuration is not a dictionary of string:int. See DESIGN.md.')
            else:
                # For each keyword, check to see if it is in the record tokens in part. If so, score the points.
                for keyword in self.conf['scoring']['interested_words']:
                    points = 0
                    try:
                        points = int(self.conf['scoring']['interested_words'][keyword])
                    except Exception as e:
                        log.debug('Keyword of interest has a non-integer value for word: ' + str(keyword))
                    if 'text' in record and keyword.lower() in record['text'].lower():
                        log.debug('Found a matching keyword: ' + str(keyword) + ' within the record.')
                        score = score + points
        # KEYWORDS of DISINTEREST
        if 'disinterested_words' in self.conf['scoring']:
            # Parse each one, provided a dictionary was given.
            if isinstance(self.conf['scoring']['disinterested_words'], dict) is False:
                log.debug('Could not score keywords of disinterest, the value provided in the configuration is not a dictionary of string:int. See DESIGN.md.')
            else:
                # For each keyword, check to see if it is in the record tokens in part. If so, score the points.
                for keyword in self.conf['scoring']['disinterested_words']:
                    points = 0
                    try:
                        points = int(self.conf['scoring']['disinterested_words'][keyword])
                    except Exception as e:
                        log.debug('Keyword of disinterest has a non-integer value for word: ' + str(keyword))
                    if 'text' in record and keyword.lower() in record['text'].lower():
                        log.debug('Found a matching keyword: ' + str(keyword) + ' within the record.')
                        score = score - points
        # TODO #17-Eliminate-Interest-and-Disinterest-Word-Scoring: Having a distinction between these two (interest and disinterest) makes no sense. Rather just a global keyword scoring allowing any positive or negative number makes better sense.
        # TODO #9-Implement Derivative Message Scoring: Re-work the index to store a flag for derived messages like re-tweets and then score them separately.
        # HASHTAG and SHOUTOUT HECK
        if 'hashtags' in record and isinstance(record['hashtags'], list) and len(record['hashtags']) > 0:
            # By getting here, there is a list of hashtags in the record that should be scored.
            hh = 0
            if 'hashtag_heck' in self.conf['scoring']:
                try:
                    hh = int(self.conf['scoring']['hashtag_heck'])
                except Exception as e:
                    log.error('Hashtag heck value in the configuration is not an integer. Won\'t score on any hashtag')
                score += (len(record['hashtags']) * hh)
        if 'references' in record and isinstance(record['references'], list) and len(record['references']) > 0:
            # By getting here, there is a list of references in the record that should be scored.
            sh = 0
            if 'shoutout_heck' in self.conf['scoring']:
                try:
                    sh = int(self.conf['scoring']['shoutout_heck'])
                except Exception as e:
                    log.error('Shoutout heck value in the configuration is not an integer. Won\'t score on any shoutout')
                score += (len(record['references']) * sh)
        # SHOUT OUTS TO ME
        if 'user_identification' in self.conf and isinstance(self.conf['user_identification'], dict) and 'social_media_handles' in self.conf['user_identification'] and isinstance(self.conf['user_identification']['social_media_handles'], list) and len(self.conf['user_identification']['social_media_handles']) > 0:
            # By getting here, there are social media handles associated with the user worth checking. 
            # If they exist in the references of the record, then additional scoring could happen.
            rtm = 0
            if 'references_to_me' in self.conf['scoring']:
                try:
                    rtm = int(self.conf['scoring']['references_to_me'])
                except Exception as e:
                    log.error('References to me value in the configuration is not an integer. Won\'t score on any reference to me.')
            if 'references' in record and isinstance(record['references'], list) and len(record['references']) > 0:
                for handle in self.conf['user_identification']['social_media_handles']:
                    for reference in record['references']:
                        if handle.lower() in reference.lower():
                            # Match. The references contain @ whereas the handles do not have to.
                            score += rtm
        log.debug('Assigning score value of: ' + str(score) + ' to the record')
        return score

import logging
import json
from _tkinter import create
from builtins import None

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
        log.debug('Attempting to load configFile: '+configFile+' and any global.json found in that folder.')
        self.conf = {}
        if configFile is None:
            log.error('Failed to load configuration file, None was passed in as a parameter to ConfigFileHelper. An empty configuration dictionary will result.')
            return
        parts = configFile.split('/')
        globalJsonFile = '/'.join(parts[:len(parts)-1])+'/global.json'
        try:
            with open(globalJsonFile) as f:
                data = json.load(f)
                for key in data:
                    self.conf[key] = data[key]
            log.debug('Loaded global.json file found at: '+globalJsonFile)
        except Exception as e:
            # Failed to load global.json. It may not exist, or other problem.
            log.warn('Failed to load: '+globalJsonFile+'. Proceeding to load configFile on itself. Exception is: '+str(e))
        # And now load configFile on top of this.
        try:
            with open(configFile) as f:
                data = json.load(f)
                for key in data:
                    self.conf[key] = data[key]
        except Exception as e:
            log.error('Failed to load: '+configFile+". This will result in an empty configuration. Exception is: "+str(e))
        log.info('Loaded configuration file: '+configFile+' successfully.')
        
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
    
    def storeData(self, author=None, authorLocation=None, authorScreenName='Unknown', createdAt=None, hashtags=[], localityConfidence=0.0, location='', placeName=None, placeFullName=None, polarity=None, references=[], source=None, sentiment=None, subjectivity=None, text=None, tokens=[])
        '''
        Stores data given into ElasticSearch.
        
        -- author string, the name of the author. Optional, not required to be put into the index.
        -- authorLocation string, the location of the author. Optional, not required to put into the index.
        -- authorScreenName string, the social media handle or screen name. Optional, if not provided then 'Unknown' is used.
        -- createdAt string, the date and time the tweet was made in ISO 8601 format. Required, without it we can't really query it back. If not provided then a DEBUG log will be made and nothing done. ISO 8601 formatting is not enforced by this method. Providing anything else would cause the message to be indexed but never found in a time based query.
        -- hashtags list of string, the hashtags used within the body of the message (e.g. #fun). Optional, if not provided then an empty list is indexed.
        -- locatlityConfidence float, a number from 0.0 to 1.0 indicating the confidence on how local to the configured location this author is physically. Required, default is 0.0. If a non-number or out of range number is provided, then a DEBUG log will be made and nothing done.
        -- placeName string, the name of the place the author of the message is. Optional, not required to be put into the index.
        -- placeNameFull string, the full unabbreviated place name the author of the message is. Optional not required to be put into the index.
        -- polatity float, a number -1.0 to 1.0. @see https://en.wikipedia.org/wiki/Sentiment_analysis. Optional, not required to be put in the index. If provided, it must be a float type and within the range. If not, it will not be put into the index.
        -- references list of string, a list of references made within the text (e.g. @johndoe). Optional, if not provided then an empty list is indexed.
        -- sentiment string, @see https://en.wikipedia.org/wiki/Sentiment_analysis. Optional, not required to be put into the index.
        -- source string, the name of the social media platform storing data. Optional, not required to be put into the index.
        -- subjectivity float, a number -1.0 to 1.0. @see https://en.wikipedia.org/wiki/Sentiment_analysis. Optional, not required to be put into the index. If provided, it must be a float type within the range. If not, it will not be put into the index.
        -- text string, the body of the message being indexed. Required, without it there is no data. If not provided, then a DEBUG log will be made and nothing done.
        -- tokens list of string, the text of the message broken down into single words for token matching purposes. Optional, if not provided then an empty list is indexed.
        '''
        body = {}
        # Check each field for None and then do the appropriate actions.
        if author is not None:
            body["author"] = author
        if authorLocation is not None:
            body["author_location"] = authorLocation
        if authorScreenName is not None:
            body["author_screen_name"] = authorScreenName
        if createdAt is not None:
            body['created_at'] = createdAt
        else:
            log.debug('Provided data to store has None createdAt. Ignoring.')
            return
        if hashtags is not None:
            body["hashtags"] = hashtags
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
            body["locality_confidence"] = lC
        if placeName is not None:
            body['place_name'] = placeName
        if placeNameFull is not None:
            body['place_name'] = placeNameFull
        if polarity is not None:
            pol = 0.0
            try:
                pol = float(polarity)
                ... m
            except:
                # Not a number. Set it to 
                
            if lC < -1.0 or lc > 1.0:
                log.debug('Provided data has a locality confidence that is not between -1.0 and 1.0 inclusive. Ignoring.')
                return

# -----

            
        myPlaceFullName = "Not Set"
        if(placeFullName is not None):
            myPlaceFullName = placeFullName
        body["place_full_name"] = myPlaceFullName
        myPlaceName = "Not Set"
        if(placeName is not None):
            myPlaceName = placeName
        body["place_name"] = myPlaceName
        body['created_at'] = createdAt
        body['text'] = text
        myLocal = "False"
        if(local is not None):
            myLocal = local
        body["local"] = myLocal
        if(sentiment is not None):
            body["sentinment"] = sentiment
        myPolarity = 0.0           
        if(polarity is not None):
            myPolarity = polarity
        body["polarity"] = myPolarity
        mySubjectivity = 0.0
        if(subjectivity is not None):
            mySubjectivity = subjectivity
        body["subjectivity"] = mySubjectivity
        body["tokens"] = tokens
        body["hashtags"] = hashtags
        body["references"] = references
        body["source"] = source
        if(location is not None):
            body["location"] = location

        try:
            es.index(index=elastic_index,
                     doc_type="test-type",
                     body=body)
        except Exception as e:
            print("ERROR: Can not index because "+str(e))
    
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
        
    def getTweetText(self, jsonDataString):
        '''
        Looks at the content of incoming tweet data in a JSON formatted string and pulls out the raw text found within.
        
        -- jsonDataString string, the JSON data from a tweet. Required, if None is passed then None is returned. If it is bad JSON, an error is thrown and None is returned.
        @return string, the raw full tweet text contained therein. None is returned jsonDataString has bad/unexpected content or there really is no tweet raw text in it.
        '''
        if jsonDataString is None:
            log.info('Tweet contains no text within it, the jsonDataString given was None.')
            return None
        try:
            dict_data = json.loads(jsonDataString)
        except Exception as e:
            log.warn('Failed to load the tweet JSON: '+str(e))
            return None
        if "extended_tweet" in dict_data:
            # Special class of Tweets have their data in this location. Check here first.
           return dict_data['extended_tweet']['full_text']
        elif 'retweeted_status' in dict_data:
            # Retweets have their text data somewhere else.
            if 'extended_tweet' in dict_data['retweeted_status'] and 'full_text' in dict_data['retweeted_status']['extended_tweet']:
                return dict_data['retweeted_status']['extended_tweet']['full_text']
        # Otherwise, try just 'text' at the top level.
        try:
            return dict_data['text']
        except Exception as e:
            # Some kind of error in getting the data.
            log.warn('Failed to find the text in the tweet because of an error: '+str(e))
            return None
        log.info('Tweet contains no text that could be found.')
        return None
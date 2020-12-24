import logging
import json

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
    '''
    
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
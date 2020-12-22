'''
This is a set of utility classes and functions designed to do the dirty work of all bot types

Created on Dec 21, 2020

@author: Michael
'''
import logging

log = logging.getLogger(__name__)

class ConfigFileHelper:
    '''
    ConfigFileHelper loads JSON configuration files and then holds on to a reference to them in memory as a dictionary of terms.
    '''
    
    def __init__(self, configFile):
        '''
        Initializes the class and loads in configuration details from the filee, @see loadConfiguration.
                
        -- configFile string, the location of the JSON config file to load. Required, without it nothing is loaded and an empty internal dictionary is set up. A warning is issued in that case.
        @see loadConfiguration
        '''
        self.conf = {}
        if configFile is None:
            log.warn('Failed to load configuration file, None was passed in as a parameter to ConfigFileHelper. An empty configuration dictionary will result.')
        else:
            loadConfiguration(configFile)
    
    def loadConfiguration(self, configFile):
        '''
        Loads configuration information into a class variable conf. First looks into the folder where configFile is and if a global.json is there, loads that into memory. Then proceeds to load configurationFile and overwrites any property that is found in global.json. This function if called more than one time will overwrite the entire conf dictionary, so be warned!
                
        -- configFile string, the location of the JSON config file to load. A global.json is not required in that folder. Required, without it nothing is loaded. A warning is issued in that case.       
        '''
        if configFile is None:
            log.warn('Failed to load configuration file, None was passed in as a parameter to loadConfiguration. Nothing happens, an empty conf dictionary could have resulted.')
            return
        parts = configFile.split('/')
        // .. join all but the first part ...

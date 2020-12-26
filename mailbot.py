import argparse
import jaraco.logging
import logging
from utils import ConfigFileHelper, ElasticSearchHelper

log = logging.getLogger(__name__)


class MailBot:
    '''
    Mail bot acts on behalf of a particular user to search over the contents of the Elastic Search index, score messages, and deliver them to an email account.
    @author: Michael
    '''

    def __init__(self, configFile): 
        '''
         Initializes the MailBot, loading the configuration file.
         
        -- configFile string, the location of the configuration JSON used to configure this bot instance. Required, without it an error log is made and nothing happens further
        '''
        if configFile is None:
            log.error("Could not initialize MailBot with None config file")
            return
        log.info("Initializing MailBot with config file: " + configFile)
        configHelper = ConfigFileHelper(configFile)
        self.conf = configHelper.getConf()
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

    def executeQueries(self):
        '''
        This method goes through every configured query and executes it on Elastic Search .....
        '''
        # Check to see if queries is set in the configuration, first.
        if 'queries' not in self.conf:
            log.warn('No queries were put in the configuration file. Nothing happens.')
            return
        for query in self.conf['queries']:
            # Execute this query in Elastic Search and print the resuts out for now
            log.debug('Query to Elastic Search is: ' + str(query))
            result = self.elasticSearchHelper.query(query)
            log.debug('Result: ' + str(result))
            # TODO -- seems to be only bringing in small quantities. Paging?
        # TODO -- now parse the results and built up scores for each of the hits.
        # TODO -- then send out the mail

def get_args():
    '''
    Uses ArgumentParser to pull options off the command line for use by MailBot    
    '''
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c",
        "--config",
        dest="config_file",
        default='run/mailbot.json',
        type=str,
        help="The mailbot.json configuration file to use",
    )
    jaraco.logging.add_arguments(parser)
    return parser.parse_args()


def main():
    '''
    Starts a MailBot instance given options off the command line using ArgumentParser
    
    @see get_args
    '''
    options = get_args()
    jaraco.logging.setup(options)
    mb = MailBot(options.config_file)
    # Now execute all queries.
    mb.executeQueries()


if __name__ == "__main__":
    '''
    This is a catch-all so that this file may be used as an entry point from Python, e.g. 'python mailbot.py'
    '''
    # Merely call main, which then parses arguments and sets up the bot
    main()

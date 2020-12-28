import argparse
import jaraco.logging
import logging
from utils import ConfigFileHelper, ElasticSearchHelper, ScoringHelper
from builtins import None

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
        # Set up the Scoring Helper.
        self.scoringHelper = ScoringHelper(self.conf)
        # Finally, define the Mailbot's global result dictionary of replies:
        self.globalReply = {}

    def executeQueries(self):
        '''
        This method goes through every configured query and executes it on Elastic Search. It calls parseResult on each query's full result which then scores the results.        

        @see parseResult
        '''
        # Check to see if queries is set in the configuration, first.
        if 'queries' not in self.conf:
            log.warn('No queries were put in the configuration file. Nothing happens.')
            return
        for query in self.conf['queries']:
            # Execute this query in Elastic Search and print the resuts out for now.
            # First check for key components of the query that have to be there for Mailbot to function.
            if 'query' not in query:
                # This is critically essential. If not there, log a warning and continue on.
                log.warning('Query doesn\'t have any "query" criteria. Skipping over: '+str(query))
                continue
            if 'title' not in query:
                # Also essential> Title is the unique ID of the query and used prominently in the e-mail
                log.warning('Query doesn\'t have any "title" criteria. Skipping over '+str(query))
                continue
            # Pull out the "query" part and stick that in its own dictionary. The rest of it is metadata needed later, e.g. 'title'
            # Elastic search will not want any of that, it just wants a dictionary with one term: "query"
            queryDict = { "query" : query["query"] }            
            log.debug('Query to Elastic Search is: ' + str(queryDict))
            result = self.elasticSearchHelper.query(queryDict)
            log.debug('Result: ' + str(result))
            # TODO -- seems to be only bringing in small quantities. Paging?
            self.parseResult(result, title, hitLimit)
        # TODO -- now parse the results and built up scores for each of the hits.
        # TODO -- then send out the mail

    def parseResult(self, result, query):
        '''
        Parses a dictionary response from Elastic Search containing multiple messages. Scores each one and puts it in the globalReply. This method can be called on partial results of the supplied query in order to manage paged results from Elastic Search.
        
        -- result dictionary, the actual reply from Elastic Search containing part of all of the query response. Required. Without this, there's nothing to do and if None a warning will be issued and nothing will happen.
        -- query dictionary, the input query dictionary from the configuration file. This contains metadata that helps parse the result and properly update globalReply. Without it, processing the result would fail and if None a warning is issued and nothing will happen.
        '''
        if result is None:
            log.warning('No result given to parseReply. Nothing will happen.')
            return 
        if query is None:
            log.warning('No input query given to parseReply. Nothing will happen.')
            return
        # Set up entry in the globalReply first, if it doesn't already exist.
        # This requires title to be in the input query as that is the key in the dictionary.
        if 'title' not in query:
            # Also essential> Title is the unique ID of the query and used prominently in the e-mail
            log.warning('Query doesn\'t have any "title" criteria. Skipping over parsing results for '+str(query))
            continue
        if query['title'] not in self.globalReply:
            # First time set up. Copy in the original query contents because later we'll need the metadata when sending out the mail.
            globalReply[query['title']] : {}
            globalReply[query['title']]['originalQuery'] : query
        # Now score the results found in the result list.
        score = self.scoringHelper.scoreContent(result)
        # Now put that in the globalReply appropriately.
        # -------------- DESIGN THIS NEXT ----------------------
        
    def sendMail(self):
        '''
        Sends the mail...
        '''
        return

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

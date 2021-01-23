import poplib
import string, random
import StringIO, rfc822
from utils import ConfigFileHelper, ElasticSearchHelper

class ReplyBot:
'''
Reply bot periodically checks an email account for response e-mails from a user. When this happens, it will find the corresponding media to reply to and issue the response.
@author: Michael
'''
   
    def __init__(self, configFile): 
    '''
    Initializes the ReplyBot, loading the configuration file. It sets up internal class data fields as per the DESIGN.md.
    
    -- configFile string, the location of the configuration JSON used to configure this bot instance. Required, without it an error log is made and nothing happens further.
    -- @see DESIGN.md
    '''
        if configFile is None:
            log.error("Could not initialize ReplyBot with None config file")
            return
        log.info("Initializing ReplyBot with config file: " + configFile)
        configHelper = ConfigFileHelper(configFile)
        self.conf = configHelper.getConf()
        # Check for critical things needed in the configuration.
        if 'email' not in self.conf:
            log.error('No email section found in the configuration. Failing out.')
            return
        if 'password' not in self.conf['email']:
            log.error('No password set in the email section in the configuration. Failing out.')
            return
        if 'server' not in self.conf['email']:
            log.error('No server set in the email section in the configuration. Failing out.')
            return 
        if 'username' not in self.conf['email']:
            log.error('No username set in the email section in the configuration. Failing out.')
            return
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
    
    def readMail():
        '''
        '''
        # Connect to server
        try:
            server = poplib.POP3(self.conf['email']['server'])
        except Exception as e:
            log.error('Failed to connect to sever via POP3. No mail downloaded or read.',e)
            return
        # Login
        try:
            server.user(self.conf['email']['username'])
            server.pass_(self.conf['email']['password'])
        except Exception as e:
            log.error('Failed to log in with supplied username and password in configuration. No mail downloaded or read.',e)
            return
        # List items on server
        resp = None
        items = None
        octets = None
        try:
            resp, items, octets = server.list()
        except Exception as e:
            log.error('Failed to list items on the server. No mail downloaded or read.',e)
            return
        # Now actually pull them down, one at a time
                       
        for i in range(0,1):
            id, size = string.split(items[i])
            resp, text, octets = server.retr(id)
    
             text = string.join(text, "\n")
             file = StringIO.StringIO(text)
        
            message = rfc822.Message(file)
        
            for k, v in message.items():
                print k, "=", v

def get_args():
    '''
    Uses ArgumentParser to pull options off the command line for use by ReplyBot    
    '''
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c",
        "--config",
        dest="config_file",
        default='run/replybot.json',
        type=str,
        help="The replybot.json configuration file to use",
    )
    jaraco.logging.add_arguments(parser)
    return parser.parse_args()


def main():
    '''
    Starts a ReplyBot instance given options off the command line using ArgumentParser
    
    @see get_args
    '''
    options = get_args()
    jaraco.logging.setup(options)
    rb = ReplyBoot(options.config_file)
    # TODO: More actions here

if __name__ == "__main__":
    '''
    This is a catch-all so that this file may be used as an entry point from Python, e.g. 'python replybot.py'
    '''
    # Merely call main, which then parses arguments and sets up the bot
    main()

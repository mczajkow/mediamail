import argparse
import email.utils
import io
import jaraco.logging
import logging
import poplib
import string, random
from utils import ConfigFileHelper, ElasticSearchHelper

log = logging.getLogger(__name__)


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
    
    def processMessage(self, deliToken, messageBody):
        '''
        Takes in a deliToken and the contents of the body of the message preceding the deliToken, just after the closing ] mark. Processes the contained command (if any).

        -- deliToken string, 5 characters in length. Required. Without this, nothing is processed and a warning issued.
        -- messageBody string, the contents of the command message to give to the referenced deliToken.
        '''
        continue
    
    def processEmail(self, message):
        '''
        Takes in an array of bytes of strings that comprise the raw body of the email message. It assembles the email body and then looks for deli tokens in there. If any are found, processMessage is then called.
        
        -- message array of bytes, each byte is convertable into a string. Required, if None is passed, a warning is issued and nothing happens.
        @see processDeliToken
        '''
        if message is None or isinstance(message, list) is False:
            log.warning(msg)('No message passed in, doing nothing with the email.')
            return
        # Parse out the garbage in each line.
        cleanedMessage = ""
        for line in message:
            cleanedLine = ""
            # Lines begin with b' or b"
            cleanedLineParts1 = str(line).split("b'")
            cleanedLineParts2 = str(line).split('b"')
            if len(cleanedLineParts1) > 1:
                # Most cases are here.
                cleanedLine = cleanedLineParts1[1]
                cleanedLine = cleanedLine[:len(cleanedLine) - 1]            
            elif len(cleanedLineParts1) == 1 and len(cleanedLineParts2) > 1:
                # The alternate, starts with b" is then used.
                cleanedLine = cleanedLineParts2[1]
                cleanedLine = cleanedLine[:len(cleanedLine) - 1]
            # else: If anything else, just skip that line.
            cleanedMessage += cleanedLine
        # Now, the result of this is to have a glob of text that needs parsing for the [ and ] of the deli token.
        parsed = cleanedMessage.split('[')
        for part in parsed:
            if len(part) > 6:
                # OK, it could be a deli token. Check for ending.
                if part[5] == ']':
                    # Good, now pull out the contents and do a deli token check.
                    token = part[:5]
                    log.debug('Found potential deli token: ' + token)
                    # Special case check: 'class' is not a valid token.
                    if token == "class":  # add more as needed.
                        log.debug('Skipping special case token')
                        continue
                    # Now process the entire part1 as it now may contain additional information.
                    processMessage(token, part.split(']')[1])
                else:
                    # Not a deli token, the 6th character is not a ] closer. Ignore.
                    continue
            else:
                # Doesn't have at least 6 characters afterwards. Ignore
                continue
    
    def readMail(self):
        '''
        Connects to the configured email server, downloads mail and then utilizes the processMessage method per message.
        
        @see processMessage
        '''
        # Connect to server
        log.debug('Connecting to server...')
        try:
            server = poplib.POP3(self.conf['email']['server'])
        except Exception as e:
            log.error('Failed to connect to sever via POP3. No mail downloaded or read.', e)
            return
        # Login
        log.debug('Logging on to server...')
        try:
            server.user(self.conf['email']['username'])
            server.pass_(self.conf['email']['password'])
        except Exception as e:
            log.error('Failed to log in with supplied username and password in configuration. No mail downloaded or read.', e)
            return
        # List items on server
        resp = None
        items = None
        octets = None
        log.debug('Listing items on the server')
        try:
            resp, items, octets = server.list()
        except Exception as e:
            log.error('Failed to list items on the server. No mail downloaded or read.', e)
            return
        log.debug('Response is: ' + str(resp) + ' items are: ' + str(items) + ' octets are: ' + str(octets))
        # Now actually pull them down, one at a time
        for i in range(0, 1):
            log.debug('Pulling down an item...')
            id, size = str(items[i]).split("'")[1].split(' ')
            log.debug('ID is: ' + str(id) + ' and size is: ' + str(size))
            resp, text, octets = server.retr(id)
            self.processEmail(text)


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
    rb = ReplyBot(options.config_file)
    # TODO: More actions here
    rb.readMail()


if __name__ == "__main__":
    '''
    This is a catch-all so that this file may be used as an entry point from Python, e.g. 'python replybot.py'
    '''
    # Merely call main, which then parses arguments and sets up the bot
    main()

import argparse
import email.utils
import io
import jaraco.logging
import logging
import poplib
import string, random
from utils import ConfigFileHelper, ElasticSearchHelper, MMIDHelper, TwitterHelper
from calendar import firstweekday

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
        self.elasticSearchHelper = ElasticSearchHelper(self.conf['elastic']['host'], self.conf['elastic']['port'], self.conf['elastic']['index'], self.conf)
        log.info('Elastic Search setup complete.')
        # Set up a TwitterHelper
        self.myTwitterHelper = TwitterHelper(self.conf)
        # Finally, this class will need access to a MMIDHelper.
        self.mmidHelper = MMIDHelper(self.conf)
    
    def processEmail(self, message):
        '''
        Takes in an array of bytes of strings that comprise the raw body of the email message. It assembles the email body and then looks for mmid tokens in there. If any are found, processMessage is then called.
        
        -- message array of bytes, each byte is convertable into a string. Required, if None is passed, a warning is issued and nothing happens.
        @see processMMIDToken
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
        log.debug('Email message downloaded: ' + cleanedMessage)
        # Now, the result of this is to have a glob of text that needs parsing for the [ and ] of the mmid token.
        parsed = cleanedMessage.split('[')
        for part in parsed:
            if len(part) > 6:
                # OK, it could be a mmid token. Check for ending.
                if part[5] == ']':
                    # Good, now pull out the contents and do a deli token check.
                    token = part[:5]
                    log.debug('Found potential deli token: ' + token)
                    # Check for black listed tokens
                    if self.mmidHelper.isBlacklisted(token):
                        log.debug('Skipping blacklisted token.')
                        continue
                    # Now process the entire part1 as it now may contain additional information.
                    self.processMessage(token, part.split(']')[1])
                else:
                    # Not a deli token, the 6th character is not a ] closer. Ignore.
                    continue
            else:
                # Doesn't have at least 6 characters afterwards. Ignore
                continue
            
    def processLike(self, mmid):
        '''
        This looks up the mmid in Elastic Search and using the contents of the record, sends a "like" to that particular author for the message given.
        
        -- mmid string,  5 characters in length. Required. Without this, nothing is processed and a warning issued.
        '''
        if mmid is None or len(mmid) != 5:
            log.warning('Can not process a like to the mmid given as it was None or not length 5.')
            return 
                # Now that everything checks out on the inputs, get the MMID from Elastic Search
        matchQuery = {}
        matchQuery['query'] = {}
        matchQuery['query']['match'] = {}
        matchQuery['query']['match']['mmid'] = mmid
        log.debug('Trying to query Elastic Search for the mmid: ' + mmid)        
        elasticSearchResult = self.elasticSearchHelper.query(matchQuery)
        if elasticSearchResult is None or isinstance(elasticSearchResult, dict) is False:
            # Failed query?
            # This is actually pretty serious and needs at least WARN level, perhaps more?
            log.warning('No resulting MMID found in Elastic Search: ' + mmid)
            return  # Nothing else we can do.
        log.debug('Found result in Elastic Search')
        # Now parse out the results found in the search.
        parsedResults = self.elasticSearchHelper.parseQueryResults(elasticSearchResult, mmid)
        result = {}
        if len(parsedResults) > 0:
            result = parsedResults[0]
        else:
            # No matches found.
            # This is actually pretty serious and needs at least WARN level, perhaps more?
            log.warning('No resulting MMID found in Elastic Search: ' + mmid)
            return  # Nothing else we can do.
        # Depending on the source given, we process the like differently
        if 'source' not in result:
            log.warning('Found the MMID in Elastic Search but the record has no source (e.g. twitter) set so the like can not be processed.')
            return
        source = result['source']
        # NOTE: This is where other platforms can be added in the future.
        if source == 'twitter':
            # The ID of the tweet is at the end of the URL.
            if 'url' not in result:
                log.warning('There is no URL set in the record. For twitter, that is where the ID is and thus a like can not be processed.')
                return
            try:
                tweetId = result['url'].split('/')[len(result['url'].split('/')) - 1]
                log.debug('Liking found tweet ID: ' + str(tweetId))
                self.myTwitterHelper.favorite(tweetId)
            except Exception as e:
                # Some problem in splitting up the url?
                log.warning('Could not get the tweetId from the url: ' + str(result['url']) + '. Ignoring.')
        else:
            # Unsupported platform.
            log.warning('Record for MMID: ' + mmid + ' has an unsupported source: ' + source + ". Ignoring.")
    
    def processMessage(self, mmid, messageBody):
        '''
        Takes in a deliToken and the contents of the body of the message preceding the deliToken, just after the closing ] mark. Processes the contained command (if any).

        -- mmid string, 5 characters in length. Required. Without this, nothing is processed and a warning issued.
        -- messageBody string, the contents of the command message to give to the referenced mmid. If this is None or is zero in length, nothing happens.
        '''
        if mmid is None or len(mmid) != 5:
            log.warning('Not processing the message given because the MMID given was None or not length 5.')
            return
        if messageBody is None or len(messageBody) < 1:
            log.warning('The message supplied is None or zero length. Skipping')
            return
        # First, we look for supported commands immediately in the messageBody. If those don't exist, then we ignore.
        command = ''
        try:
            command = messageBody.lstrip().split(' ')[0]
        except Exception as e:
            # This means that there is nothing other than maybye that first leading space.
            log.warning('Failed to process command given: ' + command)
            return
        # Now process the supported commands
        if command == 'like' or command == 'favorite':
            # Supported
            self.processLike(mmid)
        elif command == 'reply':
            # Supported. Need to get the body out.
            body = ''
            try:
                bodyParts = messageBody.lstrip().split(' ')[1:]
                body = ' '.join(bodyParts)
                self.processReply(mmid, body)
            except Exception as e:
                log.warning('Failed to process reply command as nothing else was given other than the word "reply"')
        else:
            # Not supported. Log only at debug.
            log.debug('Unsupported command: ' + command)
    
    def processReply(self, mmid, body):
        '''
        This looks up the mmid in Elastic Search and using the contents of the record, sends a "like" to that particular author for the message given.
        
        -- mmid string, 5 characters in length. Required. Without this, nothing is processed and a warning issued.
        -- body string, Required. Without this, nothing can be sent back. Body is also required to start with the @author name. If either criteria is not met, a warning is issued.
        '''
        if mmid is None or len(mmid) != 5:
            log.warning('Can not process the reply command as the MMID given is None or less than 5 in length.')
            return
        if body is None or len(body) < 1:
            parts = body.split(' ')
            if len(parts) <= 1:
                # Can't have just a reply without a message.
                log.warning('Could not reply as the message given is not long enough: ' + body)
                return 
        # Now that everything checks out on the inputs, get the MMID from Elastic Search
        matchQuery = {}
        matchQuery['query'] = {}
        matchQuery['query']['match'] = {}
        matchQuery['query']['match']['mmid'] = mmid
        log.debug('Trying to query Elastic Search for the mmid: ' + mmid)        
        elasticSearchResult = self.elasticSearchHelper.query(matchQuery)
        if elasticSearchResult is None or isinstance(elasticSearchResult, dict) is False:
            # Failed query?
            # This is actually pretty serious and needs at least WARN level, perhaps more?
            log.warning('No resulting MMID found in Elastic Search: ' + mmid)
            return  # Nothing else we can do.
        log.debug('Found result in Elastic Search')
        # Now parse out the results found in the search.
        parsedResults = self.elasticSearchHelper.parseQueryResults(elasticSearchResult, mmid)
        result = {}
        if len(parsedResults) > 0:
            result = parsedResults[0]
        else:
            # No matches found.
            # This is actually pretty serious and needs at least WARN level, perhaps more?
            log.warning('No resulting MMID found in Elastic Search: ' + mmid)
            return  # Nothing else we can do.
        # Depending on the source given, we process the like differently
        if 'source' not in result:
            log.warning('Found the MMID in Elastic Search but the record has no source (e.g. twitter) set so the like can not be processed.')
            return
        source = result['source']
        # NOTE: This is where other platforms can be added in the future.
        if source == 'twitter':
            # We need the tweetID and the author found in the body. Then, the message which is the rest of the body. See DESIGN.md
            # The ID of the tweet is at the end of the URL.
            if 'url' not in result:
                log.warning('There is no URL set in the record. For twitter, that is where the ID is and thus a like can not be processed.')
                return
            tweetId = ''
            try:
                tweetId = result['url'].split('/')[len(result['url'].split('/')) - 1]
            except Exception as e:
                # Some problem in splitting up the url?
                log.warning('Could not get the tweetId from the url: ' + str(result['url']) + '. Ignoring.')
                return 
            # Now get the author. For Twitter, it is required that the next word after the MMID is a shout-out, e.g. @johndoe
            author = ''
            parts = body.split(' ')
            if parts[0][0] != '@':
                log.warning('First word in the reply has to be an @ to direct the name of the person this goes to, for Twitter')
                return 
            author = parts[0][1:]                         
            # And then get the rest of the message.
            message = ' '.join(parts[1:])
            
            log.debug('Replying to this tweetID:' + str(tweetId) + ' to this author: ' + author + ' with this message: ' + message)
            self.myTwitterHelper.reply(tweetId, message, author)
            log.debug('Done')                
        else:
            # Unsupported platform.
            log.warning('Record for MMID: ' + mmid + ' has an unsupported source: ' + source + ". Ignoring.")
    
    def readMail(self):
        '''
        Connects to the configured email server, downloads mail and then utilizes the processMessage method per message. Deletes mail it processes.
        
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
        if len(items) == 0:
            # No mail!
            log.info('No mail to process. Try again later!')
            return
        for item in items:
            log.debug('Pulling down item id: ' + str(item))
            id, size = str(item).split("'")[1].split(' ')
            log.debug('ID is: ' + str(id) + ' and size is: ' + str(size))
            resp, text, octets = server.retr(id)
            log.info('Processing email with id: ' + str(id))
            self.processEmail(text)
            log.debug('Deleting the email with id: ' + str(id))
            deleteResponse = server.dele(id)
        # And now we're done, call quit.
        log.debug('Finishing up by calling quit on the server.')
        server.quit()
        log.info('Processed mail.')


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
    rb.readMail()


if __name__ == "__main__":
    '''
    This is a catch-all so that this file may be used as an entry point from Python, e.g. 'python replybot.py'
    '''
    # Merely call main, which then parses arguments and sets up the bot
    main()

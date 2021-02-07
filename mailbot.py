import argparse
import email.utils
import jaraco.logging
import logging
import smtplib
import ssl
import time
from email.mime.text import MIMEText
from utils import ConfigFileHelper, ElasticSearchHelper, ScoringHelper

log = logging.getLogger(__name__)


class MailBot:
    '''
    Mail bot acts on behalf of a particular user to search over the contents of the Elastic Search index, score messages, and deliver them to an email account.
    @author: Michael
    '''

    def __init__(self, configFile): 
        '''
         Initializes the MailBot, loading the configuration file. It sets up internal class data fields as per the DESIGN.md.
         
        -- configFile string, the location of the configuration JSON used to configure this bot instance. Required, without it an error log is made and nothing happens further
        -- @see DESIGN.md
        '''
        if configFile is None:
            log.error("Could not initialize MailBot with None config file")
            return
        log.info("Initializing MailBot with config file: " + configFile)
        configHelper = ConfigFileHelper(configFile)
        self.conf = configHelper.getConf()
        # Check for critical things needed in the configuration.
        if "email" not in self.conf:
            log.error('No email section found in the configuration. Failing out.')
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
        # Set up the Scoring Helper.
        self.scoringHelper = ScoringHelper(self.conf)
        # Finally, define the Mailbot's global result dictionary of replies. See DESIGN.md for details on its content structure.
        self.globalReply = []
        # Populate globalReply based on the contents of queries.
        if 'queries' not in self.conf or isinstance(self.conf['queries'], list) is False:
            log.error('No queries specified in the configuration. Nothing will be done by Mailbot.')
            return
        for query in self.conf['queries']:
            if isinstance(query, dict) is False:
                log.warning('A query in the queries configuration is not a dictionary. Rather it is: ' + str(query) + ". Skipping. See DESIGN.md")
                continue
            replyDictionary = {}
            # Set up the contents, check to ensure they are there first.
            if 'title' not in query:
                log.warning('A query in the queries configuration has no title. This is necessary. Skipping: ' + str(query))
                continue
            replyDictionary['title'] = query['title']
            replyDictionary['replies'] = []
            self.globalReply += [replyDictionary]
            
    def executeQueries(self):
        '''
        This method goes through every configured query and executes it on Elastic Search. For each reply, it calls updateGlobalReply which then updates the globalReply list.

        @see updateGlobalReply
        '''
        # Check to see if queries is set in the configuration, first.
        if 'queries' not in self.conf:
            log.warning('No queries were put in the configuration file. Nothing happens.')
            return
        # Make sure it is also a list.
        if isinstance(self.conf['queries'], list) is False:
            log.warning('Configured queries is not a list. Change the configuration and try again.')
            return
        for query in self.conf['queries']:
            # Execute this query in Elastic Search and print the resuts out for now.
            # First check for key components of the query that have to be there for Mailbot to function.
            if 'query' not in query:
                # This is critically essential. If not there, log a warning and continue on.
                log.warning('Query doesn\'t have any "query" criteria. Skipping over: ' + str(query))
                continue
            if 'title' not in query:
                # Also essential> Title is the unique ID of the query and used prominently in the e-mail
                log.warning('Query doesn\'t have any "title" criteria. Skipping over ' + str(query))
                continue
            # Pull out the "query" part and stick that in its own dictionary. The rest of it is metadata needed later, e.g. 'title'
            # Elastic search will not want any of that, it just wants a dictionary with one term: "query"
            queryDict = { "query": query["query"] }
            log.debug('Query to Elastic Search is: ' + str(queryDict))
            # Issue a scan, as we want to get all records to process.
            scanner = self.elasticSearchHelper.scan(queryDict)
            for scannedResult in scanner:
                # log.debug('Result: ' + str(aResult))
                # Each result is actually contained in the inside "_source" field.
                if isinstance(scannedResult, dict) is False or '_source' not in scannedResult:
                    # Not what we're expecting.
                    log.debug('Failed to process result, no _source found in the result from query!')
                    continue
                reply = scannedResult['_source']
                # Now update the global reply for this query.
                self.updateGlobalReply(reply, query)

    def prepareRecord(self, record, score=0):
        '''
        Creates a record to be put into the globalReply from an Elastic Search record passed in. See DESIGN.md for more information.
        
        -- record dictionary, an Elastic Search stored record. Required, if not given then None is returned.
        -- score integer, the score of this record, see utils.ScoringHelper for more information. Optional, if not provided than a default 0 is used.
        @return: dictionary or None. Dictionary containing the information meant for the email, see DESIGN.md, to be put into globalReply. None if the input record is bad.
        '''
        if record is None or isinstance(record, dict) is False:
            return None
        prepared = {}
        prepared['score'] = score
        if 'text' in record:
            prepared['text'] = record['text']
        else:
            log.warning('No text data found in Elastic Search record: ' + str(record))
            return None
        if 'mmid' in record:
            prepared['mmid'] = record['mmid']
        else:
            log.warning('No Media Mail ID (mmid) found in Elastic Search record: ' + str(record))
            return None
        if 'url' in record:
            prepared['link'] = record['url']
        if 'author_screen_name' in record:
            prepared['author_screen_name'] = record['author_screen_name']
        return prepared

    def sendMail(self):
        '''
        Takes what is currently in the globalReply and sends it to the user.
        '''
        # Check configuration for critically needed values.
        # SMTP Host, Port, User and Sender Address check
        if 'smtp_host' not in self.conf['email'] or self.conf['email']['smtp_host'] is None:
            # No host, no email.
            log.error('Could not send email, no SMTP host set in configuration.')
            return
        if 'smtp_port' not in self.conf['email'] or self.conf['email']['smtp_port'] is None:
            # No port, no email.
            log.error('Could not send email, no SMTP port set in configuration.')
            return
        if 'user_address' not in self.conf['email'] or self.conf['email']['user_address'] is None:
            # No sender address, no email.
            log.error('Could not send email, no user address set in configuration.')
            return
        if 'sender_address' not in self.conf['email'] or self.conf['email']['sender_address'] is None:
            # No sender address, no email.
            log.error('Could not send email, no sender address set in configuration.')
            return
        # Prepare the header
        header = "MediaMail Email"
        if 'title' in self.conf['email'] and self.conf['email']['title'] is not None:
            header = self.conf['email']['title']
        # Generate the body
        body = "\n"
        for reply in self.globalReply:
            # Set the reply title...
            replyTitle = "Unspecified Title"
            if 'title' in reply and reply['title'] is not None:
                replyTitle = reply['title']
            body += replyTitle + "\n"
            # Generate a line for each of the replies
            for line in reply['replies']:
                screenName = "Unknown"
                if 'author_screen_name' in line and line['author_screen_name'] is not None:
                    screenName = line['author_screen_name']
                message = "Unspecified Message"
                if 'text' in line and line['text'] is not None:
                    message = line['text']
                link = " "
                # Link is optional, it doesn't have to be there.
                if 'link' in line and line['link'] is not None:
                    link = ' (' + line['link'] + '):'
                mmid = "[NONE]"
                if 'mmid' in line and line['mmid'] is not None:
                    mmid = line['mmid']
                score = 0
                if 'score' in line and line['score'] is not None:
                    score = line['score']
                # TODO #14-Debug-Info-in-Mailbot-Emails: Put debug information like score in optionally.
                body += screenName + ': ' + message + link + '[' + mmid + '] [' + str(score) + ']\n'
            body += "\n"  # Separator for the next reply.
        # Prepare the footer
        footer = ""
        # Assemble the full body
        fullBody = header + '\n' + body + '\n' + footer
        # Remove all characters not ascii.
        fullBody = fullBody.encode('ascii', errors='ignore')
        # Now gather the meta data and put into a MIMEText
        smtp_host = self.conf['email']['smtp_host']
        smtp_port = int(self.conf['email']['smtp_port'])
        sender_email = self.conf['email']['sender_address']
        user_email = self.conf['email']['user_address']    
        smtp_username = None
        if 'smtp_username' in self.conf['email'] and self.conf['email']['smtp_username'] is not None:
            smtp_username = self.conf['email']['smtp_username']
        smtp_password = None
        if 'smtp_password' in self.conf['email'] and self.conf['email']['smtp_password'] is not None:
            smtp_password = self.conf['email']['smtp_password']
        # Create the header MIMEText
        eml = MIMEText(fullBody, _charset='UTF-8')
        eml['Subject'] = 'Your Latest Social Media Search Results'
        eml['Message-ID'] = email.utils.make_msgid()
        eml['Date'] = email.utils.formatdate(localtime=1)
        eml['From'] = sender_email
        eml['To'] = user_email
        # Send tha mail
        context = ssl.create_default_context()
        # Keep trying until we succeed.
        nextAttempt = 10.0            
        while True:
            try:
                with smtplib.SMTP(smtp_host, smtp_port) as server:
                    server.ehlo()  # Can be omitted
                    server.starttls(context=context)
                    server.ehlo()  # Can be omitted
                    # Only log on if username and password is presented.
                    if smtp_username is not None and smtp_password is not None:
                        log.debug("Logging on with configured username: " + smtp_username + " and password.")
                        server.login(smtp_username, smtp_password)
                    log.debug('Attempting to send message from: ' + str(sender_email) + ' to user email: ' + str(user_email) + " Message is: " + eml.as_string())
                    server.sendmail(eml['From'], { eml['To'], sender_email }, eml.as_string())
                    # If we get here then the email was sent.
                    log.debug('Sent Successfully!')
                    break
            except Exception as e:
                # OK. Try again, but not forever..
                if nextAttempt > 2600:
                    # Doing the math, the user has now waited 42 minutes after 6 retries.
                    log.error('Failed to send message: ' + str(e) + ". Have tried now for more than 40 minutes. Giving up.")
                    break
                log.error('Failed to send message: ' + str(e) + ". Trying again in " + str(int(nextAttempt)) + " seconds.")
                time.sleep(nextAttempt)
                # Now double the next attempt.
                nextAttempt = nextAttempt * 2
    
    def sortReplies(self, replyList):
        '''
        Used in the built-in sorted methof of Python. It utilizes the 'score' of the replyList.
        
        -- replyList list, see DESIGN.md. The replyList is what goes into the "replies" part of each globalReply record. Required, without it a 0 is returned.
        @return will return the 'score' found in the replyList, or 0 if there is no score found.
        '''
        if replyList is None or 'score' not in replyList:
            return 0
        return replyList['score']

    def updateGlobalReply(self, record, query):
        '''
        Updates the global reply dictionary that contains all results to be mailed to the user.

        -- record dictionary, a data record stored in Elastic Search's index that is to be scored and put into the global reply. Required. Without this there's nothing to do and a warning is issued before returning.
        -- query dictionary, the query in the configuration used to generate this record as returning from a query to Elastic Search. Metadata found within the query is used to update the global reply. Required. Without this there is nothing to do and a warning is issued before returning.
        '''
        if record is None:
            log.warning('No record given to updateGlobalReply. Nothing will happen.')
            return 
        if query is None:
            log.warning('No input query given to parseReply. Nothing will happen.')
            return
        # This requires title to be in the input query as that is the key in the dictionary.
        if 'title' not in query:
            # Also essential> Title is the unique ID of the query and used prominently in the e-mail
            log.warning('Query doesn\'t have any "title" criteria. Skipping over parsing results for ' + str(query))
            return
        # The hit limit needs to be there too, or use the default.
        hit_limit = 10
        if 'hit_limit' not in query:
            log.debug('Unspecified hit limit in the query entitled: ' + str(query['title']) + ". Using default of 10.")
        else:
            hit_limit = int(query['hit_limit'])
        # The author screen name should be there, or use Unidentified
        screen_name = "Unidentified"
        if 'author_screen_name' not in record:
            log.debug('Unspecified screen name in the query reply. Using the Unidentified default.')
        else:
            screen_name = record['author_screen_name']            
        # Look up the replies entry in globalReply to use. See DESIGN.md for more information on the content.
        replyToUse = None
        for reply in self.globalReply:
            if reply['title'] == query['title']:
                replyToUse = reply
        # Ensure that we have found the replyToUse before going forward.
        if replyToUse is None:
            # Didn't find it?
            log.warning('Did not find the reply for query title: ' + query['title'] + ' in the globalReply. The class wasn\'t set up right. Skipping updateGlobalReply for this title.')
            return
        repliesList = replyToUse['replies']
        # Now scan over all of the existing replies in this list to see if the text has already been set (e.g. a duplicate message). If so, don't go further.
        if 'text' not in record or len(record['text']) == 0:
            # The elastic search data is empty. Nothing to compare duplicates for or score.
            log.debug('Ignoring message stored in Elastic Search because it has no text content.')
            return
        for listItem in repliesList:
            # Note: listItem's text will be set otherwise it could not have been added into the list already. This check is done later.
            if hash(listItem['text']) == hash(record['text']):
                # It is a duplicate.
                log.debug('Duplicate record text found from the query. Ignoring the same message text.')
                return
        # Next, the score is needed to ascertain where it goes in the replyToUse's replies list (or if at all).
        scoreOfRecord = self.scoringHelper.scoreContent(record)
        # Add the item at the end of the replies list.
        preparedRecord = self.prepareRecord(record, scoreOfRecord)
        if preparedRecord is not None:
            repliesList += [preparedRecord]
        else:
            log.warning('The incoming match from Elastic Search was missing data. Skipping as part of the mail to the user.')
        # Sort the list based on the "score" contained.
        sortedList = sorted(repliesList, key=self.sortReplies, reverse=True)
        # Chop off the items at the end of the list if they exceed hit_limit.
        choppedList = sortedList[:hit_limit]
        # Put that choppedList back into the globalReply.
        # TODO: I think we could just use the replyToUse.
        for reply in self.globalReply:
            if reply['title'] == query['title']:
                reply['replies'] = choppedList


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
    log.info('Executing all configured queries.')
    mb.executeQueries()
    log.info('Sending mail')
    mb.sendMail()
    log.info("Sent. Done!")


if __name__ == "__main__":
    '''
    This is a catch-all so that this file may be used as an entry point from Python, e.g. 'python mailbot.py'
    '''
    # Merely call main, which then parses arguments and sets up the bot
    main()

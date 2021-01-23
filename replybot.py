import poplib
import string, random
import StringIO, rfc822

class ReplyBot:
'''
Reply bot periodically checks an email account for response e-mails from a user. When this happens, it will find the corresponding media to reply to and issue the response.
@author: Michael
'''
    
    def readMail():
        SERVER = "YOUR MAIL SERVER"
        USER = "YOUR USERNAME EMAIL@EMAIL.COM"
        PASSWORD = "YOUR PASSWORD"
    
        # connect to server
        server = poplib.POP3(SERVER)
    
        # login
        server.user(USER)
        server.pass_(PASSWORD)
    
        # list items on server
        resp, items, octets = server.list()
    
        for i in range(0,1):
            id, size = string.split(items[i])
            resp, text, octets = server.retr(id)
    
             text = string.join(text, "\n")
             file = StringIO.StringIO(text)
        
            message = rfc822.Message(file)
        
            for k, v in message.items():
                print k, "=", v
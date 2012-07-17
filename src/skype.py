#!/usr/bin/python
import Skype4Py
import sys
import json
import platform

def Send(msg):
    sys.stdout.write(json.dumps(msg) + '\n')
    sys.stdout.flush()

def OnMessageStatus(message, status):

    global skype

    message_body = False
    if status == Skype4Py.cmsSending:
        if (hasattr(skype,"_NextMessageIsFromBot") and skype._NextMessageIsFromBot):
            skype._NextMessageIsFromBot = False
            return
        message_body = message.Body

    if status == Skype4Py.cmsReceived:
        message_body = message.Body

    if not message_body:
        return

    Send({
        'user': message.Sender.Handle,
        'message': message_body,
        'room': message.Chat.Name,
    })

def LogMessage(message):
    Send({
        'type': 'log',
        'message': message
    })


if platform.architecture()[0][0:5] != '32bit':
    LogMessage('WARNING: python version is not 32bit this might cause Skype4Py to hang on attaching')

skype = Skype4Py.Skype()

# Starting Skype if it's not running already..
if not skype.Client.IsRunning:
    LogMessage('Starting Skype')
    skype.Client.Start()

skype.FriendlyName = 'Hubot_Skype'

LogMessage('Attaching Skype')
skype.Attach()
LogMessage('Connected to Skype as: '+skype.CurrentUser.FullName+' ('+str(skype.CurrentUser.OnlineStatus)+')')

skype.OnMessageStatus = OnMessageStatus

# wait forever until Ctrl+C (SIGINT) is issued
while True:

    line = sys.stdin.readline()
    try:
        msg = json.loads(line)
        chat = skype.Chat(msg['room'])
        skype._NextMessageIsFromBot = True
        chat.SendMessage(msg['message'])
    except KeyboardInterrupt:
        raise
    except:
        continue

    time.sleep(1)

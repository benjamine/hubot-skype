#!/usr/bin/python
import Skype4Py
import sys
import os
import re
from datetime import datetime
import json
import threading
import platform
import time
import urllib2
import traceback
import subprocess
import tempfile
from sets import Set

audioFolder = 'audio'
if os.environ.has_key('HUBOT_SKYPE_AUDIO_FOLDER'):
    audioFolder = os.environ['HUBOT_SKYPE_AUDIO_FOLDER']

transport = None
if os.environ.has_key('HUBOT_SKYPE_TRANSPORT'):
    transport = os.environ['HUBOT_SKYPE_TRANSPORT']

callMetadata = {}

def Send(msg):
    sys.stdout.write(json.dumps(msg) + '\n')
    sys.stdout.flush()

def GetCallMetadata(call):
    global onCallStartHandlers
    callUsers = Set([p.Handle for p in call.Participants])
    callUsers.add(call.PartnerHandle)
    callKey = ','.join(callUsers)
    metadata = {}
    if not callMetadata.has_key(callKey):
        LogMessage('creating metadata for call: ' + callKey)
        callMetadata[callKey] = metadata
    else:
        LogMessage('found metadata for call: ' + callKey)
        metadata = callMetadata[callKey]
    return metadata

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
    message.MarkAsSeen()

def LogMessage(message):
    Send({
        'type': 'log',
        'message': message
    })

def GetChatFromCall(call):
    global skype
    callUsers = Set([p.Handle for p in call.Participants])
    callUsers.add(call.PartnerHandle)
    for chat in skype.ActiveChats:
        chatUsers = Set([user.Handle for user in chat.Members])
        chatUsers.remove(skype.CurrentUserHandle)
        if callUsers == chatUsers:
            return chat
    # not found, create one
    LogMessage('Creating chat with ' + ','.join(callUsers))
    return skype.CreateChatWith(*callUsers)

def GetCallFromChat(chat, placeCallIfNotFound = False):
    global skype
    chatUsers = Set([user.Handle for user in chat.Members])
    chatUsers.remove(skype.CurrentUserHandle)
    for call in skype.ActiveCalls:
        callUsers = Set([p.Handle for p in call.Participants])
        callUsers.add(call.PartnerHandle)
        if chatUsers == callUsers:
            return call
    if placeCallIfNotFound:
        # not found, create one
        callUsers = chatUsers
        LogMessage('Call starting with ' + ','.join(callUsers))
        return skype.PlaceCall(*callUsers)
    else:
        LogMessage('Call not found with ' + ','.join(chatUsers))

def GetCallWith(handle, placeCallIfNotFound = False):
    global skype
    users = Set([handle])
    for call in skype.ActiveCalls:
        callUsers = Set([p.Handle for p in call.Participants])
        callUsers.add(call.PartnerHandle)
        if users == callUsers:
            return call
    if placeCallIfNotFound:
        # not found, create one
        callUsers = users
        LogMessage('Call starting with ' + ','.join(callUsers))
        return skype.PlaceCall(*callUsers)
    else:
        LogMessage('Call not found with ' + ','.join(users))

def OnCallStatus(call, status):
    LogMessage('Call with ' + call.PartnerDisplayName + ' status: ' + status)

    # handle calls as chat rooms
    Send({
        'user': call.PartnerHandle,
        'message': '[call:' + status + ']',
        'room': GetChatFromCall(call).Name
    })

    if status == Skype4Py.clsInProgress:
        call.MarkAsSeen()
        LogMessage('Call started')
        metadata = GetCallMetadata(call)
        if metadata.has_key('playonstart'):
            if metadata.has_key('afterStartRecordAndNotify'):
                metadata['afterAudioPlayed'] = 'record'
            else:
                metadata['afterAudioPlayed'] = 'hangup'
            PlayAudio(call, metadata['playonstart'])
            del metadata['playonstart']
        elif metadata.has_key('speakonstart'):
            if metadata.has_key('afterStartRecordAndNotify'):
                metadata['afterAudioPlayed'] = 'record'
            else:
                metadata['afterAudioPlayed'] = 'hangup'
            Speak(call, metadata['speakonstart'])
            del metadata['speakonstart']

def OnCallInputStatusChanged(call, active):
    # shut up if the call ends
    if call.InputDevice(Skype4Py.callIoDeviceTypeFile) == None or not active:
        metadata = GetCallMetadata(call)
        if metadata.has_key('afterAudioPlayed'):
            if metadata['afterAudioPlayed'] == 'hangup':
                LogMessage('audio played, now hanging up')
                call.Finish()
            if metadata['afterAudioPlayed'] == 'record':
                if not hasattr(call, 'recording'):
                    LogMessage('audio played, now recording answer')
                    RecordAudio(call)
    if not active:
        call.InputDevice(Skype4Py.callIoDeviceTypeFile, None)


def OnCallOutputStatusChanged(call, active):
    # shut up if the call ends
    if call.OutputDevice(Skype4Py.callIoDeviceTypeFile) == None or not active:
        if hasattr(call, 'recording'):
            RecordAudioStop(call, call.recording)
    if not active:
        call.OutputDevice(Skype4Py.callIoDeviceTypeFile, None)

def RecordAudio(call, maxSeconds = 900):
    global skype

    if not hasattr(call, 'recording'):
        participants = Set([re.sub('[^A-Za-z0-9]', '_', p.Handle) for p in call.Participants])
        participants.add(call.PartnerHandle)
        folder = os.path.abspath(os.path.join(audioFolder, 'recordings', '+'.join(participants), datetime.utcnow().date().isoformat().replace(':', '-')))
        if not os.path.isdir(folder):
            os.makedirs(folder)
        num = 0
        filenameStart =  datetime.utcnow().time().isoformat().replace(':', '-')
        filename = os.path.join(folder, filenameStart + '.wav')
        while (os.path.isfile(filename)):
            num += 1
            filename = os.path.join(folder, filenameStart + '-' + str(num) + '.wav')

        LogMessage('Recording to: ' + filename)
        call.OutputDevice(Skype4Py.callIoDeviceTypeFile, filename)

        metadata = GetCallMetadata(call)
        if metadata.has_key('afterStartRecordAndNotify'):
            user, room = metadata['afterStartRecordAndNotify'].split(',')
            Send({
                'user': user,
                'message': '[call-recording:' + filename + ']',
                'room': room
            })

        call.recording = filename

        if (maxSeconds < 1):
            maxSeconds = 1
        timer = threading.Timer(maxSeconds, RecordAudioStop, [call, filename])
        timer.start()

    Send({
        'user': call.PartnerHandle,
        'message': '[call-recording:' + filename + ']',
        'room': GetChatFromCall(call).Name
    })


def RecordAudioStop(call, filename):
    if hasattr(call, 'recording'):
        outputFilename = call.recording
        if (not outputFilename is None) and (filename is None or filename == outputFilename):
            LogMessage('Saved to: ' + outputFilename)
            call.OutputDevice(Skype4Py.callIoDeviceTypeFile, None)
            del call.recording
            Send({
                'user': call.PartnerHandle,
                'message': '[call-recorded:' + outputFilename + ']',
                'room': GetChatFromCall(call).Name
            })

def PlayAudio(call, filename):
    filename = os.path.abspath(os.path.join(audioFolder, filename))
    if not os.path.isfile(filename):
        LogMessage('File not found: ' + filename)
    else:
        LogMessage('Playing audio file ' + filename)
        call.InputDevice(Skype4Py.callIoDeviceTypeFile, filename)

def CallAndPlay(handle, filename, recordAndNotify = False):
    call = GetCallWith(handle, True)
    if call.Status == Skype4Py.clsInProgress:
        PlayAudio(call, filename)
    else:
        metadata = GetCallMetadata(call)
        metadata['playonstart'] = filename
        if (not recordAndNotify is False):
            metadata['afterStartRecordAndNotify'] = recordAndNotify
    return call

def CallAndSpeak(handle, text, recordAndNotify = False):
    LogMessage('getting call with ' + handle)
    call = GetCallWith(handle, True)
    if call.Status == Skype4Py.clsInProgress:
        LogMessage('Active call already in progress, speaking now')
        Speak(call, text)
    else:
        metadata = GetCallMetadata(call)
        metadata['speakonstart'] = text
        if (not recordAndNotify is False):
            metadata['afterStartRecordAndNotify'] = recordAndNotify
    return call

def SendCallMessage(call, message, chat = None):
    global skype
    msg = message.strip()
    if msg == '[call-answer]':
        call.Answer()
    elif msg == '[call-finish]':
        call.Finish()
    elif msg == '[call-record-stop]':
        RecordAudioStop(call)
    elif msg[0:12] == '[call-record':
        maxSeconds = 20
        if msg[0:13] == '[call-record:':
            maxSeconds = int(msg[13:-1])
        RecordAudio(call, maxSeconds)
    elif msg[0:15] == '[call-and-play:':
        handle, filename = msg[15:-1].split(',', 1)
        CallAndPlay(handle, filename, handle + ',' + chat.Name)
    elif msg[0:11] == '[call-play:':
        LogMessage('playing audio...')
        PlayAudio(call, msg[11:-1])
    elif msg[0:12] == '[call-speak:':
        LogMessage('speaking...')
        Speak(call, msg[12:-1])
    elif msg[0:16] == '[call-and-speak:':
        handle, text = msg[16:-1].split(',', 1)
        CallAndSpeak(handle, text, handle + ',' + chat.Name)
    else:
        GetChatFromCall(call).SendMessage(message)

def Speak(call, text, lang = 'en'):
    textid = re.sub('[^A-Za-z0-9]', '_', text)
    folder = os.path.abspath(os.path.join(audioFolder, 'tts'))
    if not os.path.isdir(folder):
        os.makedirs(folder)
    filename = os.path.join(folder, textid + '.wav')

    # ensure this is available (only for windows)
    speakDotNetExe = os.path.join(os.path.dirname(__file__), '../lib/SpeakDotNet/SpeakDotNet')
    ttsCommand = speakDotNetExe + ' "' + text +'" "' + filename + '"'
    subprocess.call(ttsCommand)

    LogMessage('Saying "' + text + '" to the ' + call.PartnerHandle + ' call')

    LogMessage('Playing file "' + filename + '"')
    # output file to buddy's ears
    call.InputDevice(Skype4Py.callIoDeviceTypeFile, filename)

    #os.remove(TemporaryFileWAV.name)

if platform.architecture()[0][0:5] != '32bit':
    LogMessage('WARNING: python version is not 32bit this might cause Skype4Py to hang on attaching')

skype = Skype4Py.Skype(Transport=transport)

# Starting Skype if it's not running already..
if not skype.Client.IsRunning:
    LogMessage('Starting Skype')
    skype.Client.Start()

skype.FriendlyName = 'Hubot_Skype'

LogMessage('Attaching Skype')
skype.Attach()
LogMessage('Connected to Skype as: '+skype.CurrentUser.FullName+' ('+str(skype.CurrentUser.OnlineStatus)+')')

skype.OnMessageStatus = OnMessageStatus
skype.OnCallInputStatusChanged = OnCallInputStatusChanged
skype.OnCallOutputStatusChanged = OnCallOutputStatusChanged
skype.OnCallStatus = OnCallStatus

# wait forever until Ctrl+C (SIGINT) is issued
while True:

    line = sys.stdin.readline()
    try:
        msg = json.loads(line)
        room = msg['room']
        messageText = msg['message']

        chat = skype.Chat(room)
        if (messageText.strip() == '[call-start]'):
            call = GetCallFromChat(chat, True)
        elif (messageText.strip()[0:6] == '[call-'):            
            call = GetCallFromChat(chat, False)
            if not call is None or messageText.strip()[0:10] == '[call-and-':
                SendCallMessage(call, messageText, chat)
        else:            
            chat = skype.Chat(room)
            skype._NextMessageIsFromBot = True
            chat.SendMessage(messageText)
    except KeyboardInterrupt:
        raise
    except Exception as err:
        Send({
            'type':'log',
            'message':'ERROR SENDING MESSAGE: '+str(err),
            'stackTrace': traceback.format_exc()
            })
        continue

    time.sleep(1)


{Robot, Adapter, TextMessage, EnterMessage, LeaveMessage} = require('hubot')
child_process = require('child_process')

class SkypeAdapter extends Adapter

  send: (user, strings...) ->
    json = JSON.stringify
        room: user.room
        message: strings.join('\n') + '\n'
    @skype.stdin.write json + '\n'
    console.log('TO SKYPE:', json)

  reply: (user, strings...) ->
    @send user, strings...

  run: ->
    adapter = @
    stdin = process.openStdin()
    stdout = process.stdout

    pythonPath = process.env.HUBOT_SKYPE_PYTHONPATH || 'python'

    @skype = child_process.spawn(pythonPath, [__dirname + '/skype.py'])

    processData = (jsonMsg) ->
        if not jsonMsg
            return
        try
            msg = JSON.parse(jsonMsg)
        catch err
            console.log('Error parsing skype connector response: '+err)
            console.log('DATA: '+jsonMsg)
            return

        console.log('FROM SKYPE:', msg)

        if !msg.user
            console.log('SKYPE ADAPTER LOG: ', msg.message)
            return

        user = adapter.userForName(msg.user)
        if !user
            user = adapter.userForId new Date().getTime().toString()
            user.name = msg.user

        user.room = msg.room
        if !msg.message
            return
        adapter.receive new TextMessage user, msg.message

    @skype.stdout.on 'data', (data) =>
        messages = data.toString().split('\n');
        messages.forEach (msg) ->
            processData msg.trim()

    @skype.stderr.on 'data', (data) =>
        console.error 'ERROR ON SKYPE CONNECTOR: ', data.toString()

    @skype.on 'exit', (code) =>
        console.log('skype connector process exited with code ' + code)

    @skype.on "uncaughtException", (err) =>
        console.error 'ERROR ON SKYPE CONNECTOR: ', err.toString()
        @robot.logger.error err.toString()

    process.on "uncaughtException", (err) =>
        console.error 'ERROR ON SKYPE CONNECTOR: ', err.toString()
        @robot.logger.error err.toString()

    @emit "connected"

exports.use = (robot) ->
  new SkypeAdapter robot

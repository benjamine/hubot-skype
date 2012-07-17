Hubot-Skype
=========

*Skype Adapter for [Hubot](https://github.com/github/hubot)*

This allows a hubot to take control of a running skype instance using Skype4Py. 
I created this adapter because other existing alternatives where incomplete or no longer mantained.

Installing
-----------

- Install Pyhon 2.7+ *IMPORTANT*: Skype4Py only works on python for 32bit, otherwise it will hang up on attaching to Skype.
- Install Skype4Py (check http://sourceforge.net/projects/skype4py/, eg: download source and on project root folder run: '''python setup.py install''')
- you can test Skype4Py is installed correctly this way:

```
& python
Python 2.7.3 (default, Apr 10 2012, 23:24:47) [MSC v.1500 64 bit (AMD64)] on win32
Type "help", "copyright", "credits" or "license" for more information.
>>> import Skype4Py
```

(unless you get an error like ```ImportError: No module named Skype4Py```, Skype4Py is installed correctly)

- Add hubot-skype as a dependency to your hubot package.json:

```
{
  "dependencies" : {
    "hubot": ">=2.3.0",
    "hubot-skype": "git://github.com/benjamine/hubot-skype.git"
  },
}
```

- ```npm install```
- now you can ```hubot -a skype```
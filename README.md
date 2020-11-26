# pywemo-setup

This is a script to demonstrate the pywemo reset and setup functionality as well as extend it with some additional functionality such as multiple device reset and setup.
The script should work on Linux, macOS, and Windows, although some of the functionality is only currently supported on Linux.

## Firmware Warning

Starting in May of 2020, Belkin started requiring users to create an account and login to the app (Android app version 1.25).
In addition to the account, most of the app functionality now requires a connection to the cloud (internet access), even for simple actions such as toggling a switch.
All of the commands that go through the cloud are encrypted and cannot be easily inspected.
This raises the possibility that Belkin could, in the future, update Wemo device firmware and make breaking API changes that can not longer be deciphered.
If this happens, pywemo may no longer function on that device.
It would be prudent to upgrade firmware cautiously and preferably only after confirming that breaking API changes have not been introduced.

## Setup Instructions

The following commands can be used to setup a virtual environment for this script and install the required libraries.

Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Windows:

```bash
py -3 -m venv .venv
.venv/Scripts/activate.bat
python -m pip install -r requirements.txt
```

## Developing

Be sure to also install the dev dependencies to the virtual environment from the `requirements.txt` file.

## Usage

Coming soon

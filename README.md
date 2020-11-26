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

## External Requirements (for setup only)

### OpenSSL

OpenSSL is used to encrypt the password by the pywemo library (AES only).
It should be installed and available on the path via `openssl`.
If connecting to an open network (not recommended), OpenSSL is not required.

### NetworkManager (only used for --setup-all option)

The command line interface to NetworkManager, `nmcli`, is used with the --setup-all option to search for and connect to Wemo device access points.
This use of this option requires that `nmcli` is available on the path.
This functionality exists in other OSes, but has not been implented and tested.
For example, `airport` in macOS, `netsh` in Windows should be able to achieve this, as well as other Linux tools for installations without NetworkManager.

## Usage

Coming soon

## Tested Devices

This script has been tested and confirmed working with the follow devices and firmware:

| Device Type      | Market | FirmwareVersion                         |
| :--------------- | :----: | :-------------------------------------- |
| Socket (Mini)    | US     | WeMo_WW_2.00.11452.PVT-OWRT-SNSV2       |
| Lightswitch      | US     | WeMo_WW_2.00.11408.PVT-OWRT-LS          |
| Dimmer           | US     | WeMo_WW_2.00.11453.PVT-OWRT-Dimmer      |
| Insight Switch   | UK     | WeMo_WW_2.00.11483.PVT-OWRT-Insight     |
| Switch           | UK     | WeMo_WW_2.00.11408.PVT-OWRT-SNS         |
| Maker            | UK     | WeMo_WW_2.00.11423.PVT-OWRT-Maker       |

## Developing

Be sure to also install the dev dependencies to the virtual environment from the `requirements.dev.txt` file.
All code should be formatted using black with the provide pyproject.toml and cleanly pass pylint and pycodestyle

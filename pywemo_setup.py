#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Reset and setup Belkin Wemo devices without using the Belkin iOS/Android App.

python requirements:
    - pywemo, click, colorlog

This script uses click for a cli interface.  To see informational and help
message(s), you can run:
    wemo_reset_setup.py --help

Each of the Commands listed within help also have their own help
documentation with additional information, for example:
    wemo_reset_setup.py reset --help
    wemo_reset_setup.py setup --help

It is highly recommended to read each of the --help pages for details and more
information.
"""


# -----------------------------------------------------------------------------
# ---[ Imports ]---------------------------------------------------------------
# -----------------------------------------------------------------------------
import csv
import time
import shutil
import pathlib
import logging
import datetime
import platform
import subprocess
from getpass import getpass
from typing import List, Tuple

import click
import colorlog

import pywemo
from pywemo.ouimeaux_device import Device, SetupException, ResetException


# -----------------------------------------------------------------------------
LOG = colorlog.getLogger()
LOG.addHandler(logging.NullHandler())

DASHES = '-' * (shutil.get_terminal_size().columns - 11)

# context for -h/--help usage with click
CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


# -----------------------------------------------------------------------------
def setup_logger(verbose: int) -> None:
    """Logger setup."""
    handler = colorlog.StreamHandler()
    formatter = colorlog.ColoredFormatter(
        '%(log_color)s[%(levelname)-8s] %(message)s'
    )
    handler.setFormatter(formatter)
    LOG.addHandler(handler)
    if verbose == 0:
        LOG.setLevel(logging.INFO)
    elif verbose == 1:
        # include debug messages from this script, but not the talkative
        # urllib3
        LOG.setLevel(logging.DEBUG)
        logging.getLogger('urllib3.connectionpool').setLevel(logging.WARNING)
    elif verbose == 2:
        # include all debug messages
        LOG.setLevel(logging.DEBUG)
    else:
        # include all debug messages and also write the log to file
        filename = pathlib.Path('wemo_reset_setup.log')
        LOG.setLevel(logging.DEBUG)
        handler = logging.FileHandler(filename, mode='w')
        formatter = logging.Formatter('[%(levelname)-8s] %(message)s')
        handler.setFormatter(formatter)
        LOG.addHandler(handler)

    # Record some system and program information
    date_time = datetime.datetime.now().astimezone()
    date_time = date_time.strftime('%B %d, %Y, %I:%M %p (%Z)')
    platinfo = ', '.join(platform.uname())
    LOG.debug('logging started:  %s', date_time)
    # pywemo does not provide version at this time (no pywemo.__version__)
    LOG.debug('platform:  %s', platinfo)
    LOG.debug('current directory:  %s', pathlib.Path.cwd())
    if verbose > 2:
        LOG.debug('logging to file:  %s', filename.resolve())


# -----------------------------------------------------------------------------
def find_wemo_aps() -> Tuple[List[str], str]:
    """Use network manager cli to find wemo access points to connect to."""
    try:
        subprocess.run(['nmcli', 'device', 'wifi', 'rescan'], check=False)
        networks = subprocess.run(
            [
                'nmcli',
                '--get-values',
                'SSID,IN-USE,CHAN,SIGNAL,SECURITY',
                'device',
                'wifi',
            ],
            check=True,
            capture_output=True,
        )
    except FileNotFoundError as exc:
        raise SetupException(
            'nmcli command failed (NetworkManager must be installed)'
        ) from exc
    except subprocess.CalledProcessError as exc:
        try:
            LOG.error('stdout:\n%s', networks.stdout.decode().strip())
            LOG.error('stderr:\n%s', networks.stderr.decode().strip())
        except UnboundLocalError:
            pass
        raise SetupException('nmcli command failed') from exc

    args = ' '.join(networks.args)
    stdout = networks.stdout.decode().strip()
    LOG.debug('result of "%s":\nstdout:\n%s', args, stdout)

    if not stdout:
        LOG.warning('no result from nmcli, try again')

    wemo_networks = []
    current_network = ''
    for line in stdout.split('\n'):
        if not line.strip():
            continue
        ssid, in_use, channel, signal, security = line.rsplit(':', 4)
        if in_use == '*':
            LOG.debug(
                'current network: %s (channel=%s, signal=%s, security=%s)',
                ssid,
                channel,
                signal,
                security,
            )
            # it is possible that the user could be connected to multiple
            # access points - for example, if they have multiple wireless
            # cards installed and in use - but we won't bother trying to
            # decide which card to use and will simply try to reconnect them
            # back to the the first one listed as in use.
            current_network = current_network or ssid
        if ssid.lower().startswith('wemo.'):
            LOG.info(
                'expected wemo ap: %s (channel=%s, signal=%s, security=%s)',
                ssid,
                channel,
                signal,
                security,
            )
            wemo_networks.append(ssid)

    return wemo_networks, current_network


# -----------------------------------------------------------------------------
def log_details(device: Device, verbose: int = 0) -> None:
    """Log some basic details about the device."""
    # display some general information about the device that the
    # user may find useful in understanding it
    if verbose == 0:
        data_to_print = [
            ('basicevent', 'GetFriendlyName', 'FriendlyName'),
            ('basicevent', 'GetMacAddr', None),
            ('metainfo', 'GetMetaInfo', 'MetaInfo'),
        ]
    elif verbose == 1:
        data_to_print = [
            ('basicevent', 'GetFriendlyName', 'FriendlyName'),
            ('basicevent', 'GetSignalStrength', 'SignalStrength'),
            ('basicevent', 'GetMacAddr', None),
            ('firmwareupdate', 'GetFirmwareVersion', 'FirmwareVersion'),
            ('metainfo', 'GetMetaInfo', 'MetaInfo'),
            ('metainfo', 'GetExtMetaInfo', 'ExtMetaInfo'),
            ('deviceinfo', 'GetDeviceInformation', 'DeviceInformation'),
            # ('basicevent', 'GetSetupDoneStatus', None),
        ]
    else:
        data_to_print = []
        if verbose == 2:
            # skip the calls to GetApList and GetNetworkList since they are
            # slow, but do include them if higher verbose is requested
            skip_actions = {'getaplist', 'getnetworklist'}
        else:
            skip_actions = {}
        for service_name, service in device.services.items():
            for action_name in service.actions.keys():
                if action_name.lower() in skip_actions:
                    continue
                if action_name.lower().startswith('get'):
                    data_to_print.append((service_name, action_name, None))

    failed_calls = []
    for service_name, action_name, key in data_to_print:
        name = f'{service_name}.{action_name}'
        try:
            result = device.services[service_name].actions[action_name]()

            try:
                failed = result['faultstring'].lower() == 'upnperror'
                if failed:
                    # print the failed ones at the end for easier visual
                    # separation
                    failed_calls.append((name, result))
                    continue
            except KeyError:
                pass

            # try to display the requested key, but display the entire result
            # if it doesn't exist
            try:
                name = f'{service_name}.{action_name}[{key}]'
                LOG.info('    %60s: %s', name, result[key])
            except KeyError:
                LOG.info('    %60s: %s', name, result)
        except (AttributeError, KeyError, TypeError) as exc:
            # something went wrong, hard coded services may not be available on
            # all platforms, or some Get methods may require an argument
            LOG.warning(
                '    %60s: %s', f'Failed to get result for s{name}', exc
            )

    if failed_calls:
        LOG.warning(
            '    The results below resulted in an error.  This may be due to '
            'the action no longer working or that the method requires an '
            'argument.'
        )
    for name, result in failed_calls:
        LOG.info('    %60s: %s', name, result)


# -----------------------------------------------------------------------------
def connect_to_wemo_and_setup(
    wemossid: str, ssid: str, password: str, timeout: float = 20.0
) -> None:
    """Connect to a Wemo devices AP and then set up the device."""
    try:
        networks = subprocess.run(
            ['nmcli', 'device', 'wifi', 'connect', wemossid],
            check=True,
            capture_output=True,
        )
    except FileNotFoundError as exc:
        raise SetupException(
            'nmcli command failed (NetworkManager must be installed)'
        ) from exc
    except subprocess.CalledProcessError as exc:
        try:
            LOG.error('stdout:\n%s', networks.stdout.decode().strip())
            LOG.error('stderr:\n%s', networks.stderr.decode().strip())
        except UnboundLocalError:
            pass
        raise SetupException(
            'nmcli command failed (network may not exist anymore or may no '
            'longer be reachable)'
        ) from exc

    args = ' '.join(networks.args)
    stdout = networks.stdout.decode().strip()
    LOG.debug('result of "%s":\nstdout:\n%s', args, stdout)

    # short delay to make sure the connection is well established
    time.sleep(2.0)

    LOG.info('searching %s for wemo devices', wemossid)
    devices = discover_and_log_devices(only_needing_setup=True)
    for device in devices:
        device.setup(ssid=ssid, password=password, timeout=timeout)


# -----------------------------------------------------------------------------
def discover_and_log_devices(
    only_needing_setup: bool = False, verbose: int = 0
) -> List[Device]:
    """Discover and log details about devices."""
    devices = pywemo.discover_devices()
    not_setup = []
    device = None
    for device in devices:
        if only_needing_setup:
            status = device.WiFiSetup.GetNetworkStatus()['NetworkStatus']
            if status not in {'1'}:
                not_setup.append(device)
                LOG.info('found device needing setup: %s', device)
        else:
            LOG.info(DASHES)
            LOG.info('found device: %s', device)
            if verbose >= 0:
                log_details(device, verbose)

    if only_needing_setup:
        return not_setup

    if device:
        LOG.info(DASHES)
    LOG.info('found %s devices', len(devices))
    return devices


# -----------------------------------------------------------------------------
@click.group(
    context_settings=CONTEXT_SETTINGS,
    epilog=(
        'Each of the Commands listed above have their own help '
        'documentation with additional details and information.  It is highly '
        'recommended to check those help messages as well.  You can see them '
        'by specifying the command first, for example:'
        ''
        'wemo_reset_setup.py reset --help'
    ),
)
def cli() -> None:
    """Wemo script to reset and setup Wemo devices.

    This script can be used to reset and setup Belkin Wemo devices, without
    using the Belkin iOS/Android App.

    \b
    External Requirements (for setup only)
    --------------------------------------
      - OpenSSL should be installed to use this script for device setup on
        a network using encryption, as OpenSSL is used to encrypt the password
        (AES only supported in this script).
      - nmcli (NetworkManager cli) is used (only with --setup-all option) to
        find and connect to Wemo APs.
    """  # noqa: D301  # need to keep the \b without raw string for click
    pass  # pylint: disable=unnecessary-pass


# -----------------------------------------------------------------------------
@cli.command(name='list', context_settings=CONTEXT_SETTINGS)
@click.option(
    '-v',
    '--verbose',
    count=True,
    help='''Print debug messages.  Use -v to enable debug messages from this
    script, -vv to also enable debug messages from all upstream libraries,
    and -vvv to also output the log to a file.''',
)
@click.option(
    '-i',
    '--info',
    count=True,
    help='''How much information to print.  Use -i to print all actions for
    the device that start with "Get", except for those that scan for APs or
    networks (slow).  Use -ii to also include AP/network scans.  If no -i is
    provided, a smaller subset of commonly useful functions are run.''',
)
def wemo_discover(verbose: int, info: int) -> List[Device]:
    """Discover and print information about devices on current network(s)."""
    setup_logger(verbose)
    discover_and_log_devices(verbose=info + 1)


# -----------------------------------------------------------------------------
@cli.command(name='rename', context_settings=CONTEXT_SETTINGS)
@click.option(
    '-v',
    '--verbose',
    count=True,
    help='''Print debug messages.  Use -v to enable debug messages from this
    script, -vv to also enable debug messages from all upstream libraries,
    and -vvv to also output the log to a file.''',
)
@click.option(
    '-p',
    '--path',
    default='wemo_names.csv',
    type=click.Path(exists=True, dir_okay=False),
    help='''Name of a csv file to read to get mapping for device names.  The
    file should have exactly 3 columns in the order of "UDN", "IP", "Friendly
    Name".  The first row is skipped (header) and then subsequent rows are
    used.  The UDN will be checked first, then the IP (so UDN has higher
    precedence).  A blank UDN will be skipped, thus just the IP would be
    used.''',
)
def wemo_rename(verbose: int, path: str) -> None:
    """Mass rename devices from a CSV file."""
    setup_logger(verbose)
    udn_to_name = {}
    ip_to_name = {}
    with open(path, 'r', newline='') as fin:
        fin.readline()  # header
        for row in csv.reader(fin):
            if not row or len(row) < 3 or row[0].startswith('#'):
                # skip blank lines, lines without at least 3 items, and lines
                # that start with a # (ignoring whitespace)
                continue
            udn, ip, name = [i.strip() for i in row]
            if not name:
                # skip the row if no name is provided
                continue
            if udn:
                udn_to_name[udn] = name
            if ip:
                ip_to_name[ip] = name

    devices = discover_and_log_devices()
    for device in devices:
        udn = device._config.get_UDN()  # pylint: disable=protected-access
        ip = device.host
        # set by ip first and then UDN second, so UDN has higher precedence
        name = ip_to_name.get(ip, '')
        name = udn_to_name.get(udn, name)
        if name:
            LOG.info('changing %s name to: %s', device, name)
            device.basicevent.ChangeFriendlyName(FriendlyName=name)
        else:
            LOG.info(
                'no name found for device %s with UDN="%s" and IP="%s"',
                device,
                udn,
                ip,
            )


# -----------------------------------------------------------------------------
@cli.command(name='reset', context_settings=CONTEXT_SETTINGS)
@click.option(
    '-v',
    '--verbose',
    count=True,
    help='''Print debug messages.  Use -v to enable debug messages from this
    script, -vv to also enable debug messages from all upstream libraries,
    and -vvv to also output the log to a file.''',
)
@click.option('--data', is_flag=True, help='Set flag to clear device data')
@click.option(
    '--wifi',
    is_flag=True,
    help='Set flag to clear device wifi information',
)
@click.option(
    '--full',
    is_flag=True,
    help='Full factory reset/restore, implies --data and --wifi',
)
@click.option(
    '--reset-all',
    is_flag=True,
    help='''Scan network(s) for devices and reset all found devices (will be
    prompted to continue after discovery).  Note that all connected networks
    are scanned, so beware if connected to multiple networks.  For example, if
    connected via ethernet to one network and via wifi to another.''',
)
@click.option(
    '--name',
    help='''Friendly name of the device to reset.  This option is required (and
    only used) if --reset-all is NOT used.  You must be conencted to whatever
    network the device is connected to.''',
)
def click_wemo_reset(
    verbose: int,
    data: bool,
    wifi: bool,
    full: bool,
    reset_all: bool,
    name: str,
) -> None:
    """Wemo device(s) reset (cli interface).

    NOTE: You should be on the same network as the device you want to interact
    with!  To reset a device, you should be connected to whatever network the
    device is connected to.
    """
    setup_logger(verbose)
    if full:
        data = True
        wifi = True
    try:
        if reset_all:
            devices = discover_and_log_devices()
            if name is not None:
                LOG.warning(
                    'name %s ignored, all discovered devices will be reset'
                )
            if devices and click.confirm(
                f'Are you sure you want to reset all {len(devices)} devices '
                'listed above?'
            ):
                for device in devices:
                    LOG.info(DASHES)
                    try:
                        device.reset(data=data, wifi=wifi)
                    except ResetException as exc:
                        LOG.error(exc)
                        LOG.error('|-- thus skipping: %s', device)
                LOG.info(DASHES)
        elif name is not None:
            selected = None
            for device in discover_and_log_devices():
                if device.name.lower() == name.lower():
                    selected = device
                    break
            if selected is None:
                raise ResetException(f'device named "{name}" not found')
            selected.reset(data=data, wifi=wifi)
        else:
            raise ResetException('--reset-all or --name=<str> is required')
        LOG.info('devices will take approximately 90 seconds to reset')
    except ResetException as exc:
        LOG.critical(exc)


# -----------------------------------------------------------------------------
@cli.command(name='setup', context_settings=CONTEXT_SETTINGS)
@click.option(
    '-v',
    '--verbose',
    count=True,
    help='''Print debug messages.  Use -v to enable debug messages from this
    script, -vv to also enable debug messages from all upstream libraries,
    and -vvv to also output the log to a file.''',
)
@click.option(
    '--ssid',
    required=True,
    type=str,
    help='SSID of the network the Wemo device should join',
)
@click.option(
    '--password',
    default='',
    type=str,
    help='''Password for the provided SSID (skip providing this to be prompted
    for the password with a hidden/private input)''',
)
@click.option(
    '--setup-all',
    is_flag=True,
    help='''Scan for available Wemo devices and try to setup any device that
    reports it is not currently setup (requires nmcli to find and connect to
    the networks)''',
)
@click.option(
    '--name',
    help='''Friendly name of the device to setup.  This option is required (and
    only used) if --setup-all is NOT used.  You must be connected to the
    devices local network (usually of the form Wemo.Device.XXX).''',
)
def click_wemo_setup(
    verbose: int, ssid: str, password: str, setup_all: bool, name: str
) -> None:
    """Wemo device(s) setup (cli interface).

    User will be prompted for wifi password, if not provided.  If connecting
    to an open SSID, then just enter anything for the password as it will be
    ignored.  Of course, using an open network should be discouraged.

    NOTE: You should be on the same network as the device you want to interact
    with!  To setup a device, you should be connected to the devices locally
    broadcast network, usually something of the form: Wemo.Device.XXX where
    Device is the type of Wemo (e.g. Mini, Light, or Dimmer) and XXX is the
    last 3 digits of the device serial number.  The --setup-all option will
    attempt to search for all networks of the form Wemo.* and try to setup
    any Wemo it finds on those network(s) that is not already setup.

    NOTE: Wemo devices sometimes have trouble connecting to an access point
    that uses the same name (SSID) for the 2.4GHz and 5GHz signals.  Thus it is
    recommended to disable the 5GHz signal while setting up the Wemo devices,
    and then re-enabling it upon completion.
    """
    setup_logger(verbose)
    try:
        LOG.info(DASHES)
        LOG.info(
            'NOTE: If some or all devices fail to connect, try '
            're-running the same command a second time!'
        )
        LOG.info(DASHES)
        if setup_all:
            wemo_aps, current = find_wemo_aps()
            if not wemo_aps:
                raise SetupException(
                    'No valid Wemo device AP\'s found.  Try running this '
                    'again, otherwise consider directly connecting to the '
                    'devices network and using the --name option.'
                )

            if wemo_aps and click.confirm(
                f'Are you sure you want to setup all {len(wemo_aps)} '
                '"expected wemo" devices listed above?'
            ):
                LOG.info(DASHES)
                if not password:
                    password = getpass()
                for wemo_ap in wemo_aps:
                    LOG.info(DASHES)
                    try:
                        connect_to_wemo_and_setup(wemo_ap, ssid, password)
                    except SetupException as exc:
                        LOG.error(exc)
                        LOG.error('|-- thus skipping: %s', wemo_ap)
                LOG.info(DASHES)

                if current and not current.lower().startswith('wemo.'):
                    try:
                        LOG.info('attempting to reconnect host to %s', current)
                        subprocess.run(
                            ['nmcli', 'device', 'wifi', 'connect', current],
                            check=True,
                            capture_output=True,
                        )
                    except (subprocess.CalledProcessError, FileNotFoundError):
                        # just skip re-connection, the OS will likely
                        # auto-reconnect anyway
                        pass
        elif name is not None:
            selected = None
            for device in discover_and_log_devices():
                if device.name.lower() == name.lower():
                    selected = device
                    break
            if selected is None:
                raise SetupException(f'device named "{name}" not found')
            selected.setup(ssid=ssid, password=password)
        else:
            raise SetupException('--setup-all or --name=<str> is required')
    except SetupException as exc:
        LOG.critical(exc)


# -----------------------------------------------------------------------------
# Run the script
if __name__ == '__main__':
    # pylint: disable= no-value-for-parameter
    cli()


# ---[ END OF FILE ]-----------------------------------------------------------

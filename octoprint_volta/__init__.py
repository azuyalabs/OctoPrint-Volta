# coding=utf-8
from __future__ import absolute_import

import threading
import time
import requests
import socket
import re
import base64

import octoprint.plugin
import octoprint.util

from Crypto.Cipher import AES
from requests import ConnectionError
from datetime import datetime

__author__ = 'Sacha Telgenhof <me@sachatelgenhof.com>'
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'
__copyright__ = 'Copyright (C) 2018 - 2019 AzuyaLabs - Released under the terms of the AGPLv3 License'


class VoltaPlugin(octoprint.plugin.SettingsPlugin,
                  octoprint.plugin.StartupPlugin,
                  octoprint.plugin.AssetPlugin,
                  octoprint.plugin.TemplatePlugin,
                  octoprint.plugin.EventHandlerPlugin,
                  octoprint.plugin.ProgressPlugin):
    STATE_UNKNOWN = 'unknown'
    STATE_OFFLINE = 'offline'

    JOB_STATUS_SUCCESS = 'success'
    JOB_STATUS_FAILED = 'failed'
    JOB_STATUS_IN_PROGRESS = 'in_progress'

    def __init__(self):
        self._verified = False
        self._printer_state = {
            'id': '',
            'name': '',
            'state': '',
            'heatbed_temperature': {},
            'extruder_temperature': {},
            'printjob': {},
        }
        self._port = 0

    def __verify_volta(self):
        """
        Verifies the connection to the Volta REST API.

        :returns: True if a connection to the Volta REST API can be made
                  successfully; False otherwise
        :raises ValueError: When an API Token is not provided
        :raises RuntimeError: When an error occurred communicating with the
                              Volta REST API
        """

        try:
            if not self._settings.get(['api_token']):
                raise ValueError('No API Token provided')

            printer = self._printer_profile_manager.get_current_or_default()

            self._printer_state['name'] = printer['model'] if 'model' in printer else self.STATE_UNKNOWN

            # Get the IP address of this OctoPrint instance
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                # Doesn't even have to be reachable
                s.connect(('10.255.255.255', 1))
                server = s.getsockname()[0]
            except Exception as ex:
                self._logger.exception('Caught Exception: %s' % str(ex))
                server = '127.0.0.1'
            finally:
                s.close()

            # Snake Case Printer Name
            s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', printer['name'])
            s2 = re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()

            printer_address = s2.replace(
                ' ', '_') + '@' + server + ':' + str(self._port)

            # Encrypt the printer ID
            # Generate an Initialization Vector
            iv = self._settings.get(['api_token'])[:AES.block_size]
            cipher = AES.new(self._settings.get(['api_token']), AES.MODE_CFB, iv)

            # Encrypt the data using AES 256 encryption in CBC mode using the
            # key and Initialization Vector.
            encrypted = cipher.encrypt(printer_address)

            # The IV is just as important as the key for decrypting, so save
            # it with encrypted data using a unique separator (::)
            self._printer_state['id'] = base64.urlsafe_b64encode(
                encrypted + '::' + iv)

            self.__get_current_printer_state()

        except (KeyError, ValueError) as e:
            self._logger.error(str(e))
            return False

        self._logger.info('Verifying connection to %s...' % __plugin_name__)

        try:
            headers = {
                'Accept': 'application/json',
                'Authorization': 'Bearer ' + self._settings.get(['api_token']),
                'User-Agent': 'OctoPrint-Volta/' + self._plugin_version
            }
            r = requests.get(
                self._settings.get(['api_server']) + '/api/printer/verify', headers=headers)

            # Check for proper responses (200 or 401)
            if r is not None and r.status_code not in [200, 401]:
                raise RuntimeError(
                    'Error while trying to verify the API Token with the %s service (StatusCode: %s)' % (
                        __plugin_name__, r.status_code))

            response = r.json()

            # If the returned API Token is the same, we're all good!
            if 'api_token' in response and response['api_token'] == self._settings.get(['api_token']):
                self._verified = True
                self._logger.info('Connection to %s verified.' %
                                  __plugin_name__)

                return True

        except RuntimeError as ex:
            self._logger.error(str(ex))

        except ConnectionError:
            self._logger.error('Unable to connect to the Volta Server (%s).' % self._settings.get(['api_server']))

        self._logger.warning(
            'Verification was unsuccessful. Please check if a correct API Token was provided.')

        return False

    def __notify_event(self):
        """
        Processes the event for notification to the Volta REST API.
        The message is sent asynchronously to avoid any blocking of the main
        process.

        :returns: void
        """

        # Don't send a message if we haven't been verified (yet)
        if not self._verified and not self.__verify_volta():
            return

        # Send the message async
        try:
            thread = threading.Thread(
                target=self.__send_message,
                args=(
                    self._settings.get_int(['retry']),
                    self._settings.get_int(['time_retry']),
                )
            )
            thread.daemon = True
            thread.start()

        except Exception as e:
            self._logger.exception(str(e))

    def __send_message(self, retry, sleep):
        """
        Sends the actual message (printer state) to the Volta REST API.

        :param retry: the number of tries for sending the message
        :param sleep: the number of seconds to wait before the next attempt to
                      send a message
        :returns: void
        """

        self._logger.debug('Start sending message...')

        headers = {'Accept': 'application/json',
                   'Authorization': 'Bearer ' + self._settings.get(['api_token']),
                   'User-Agent': 'OctoPrint-Volta/' + self._plugin_version
                   }

        for i in range(retry):
            self._logger.debug('Attempt: %s' % str(i + 1))

            try:
                r = requests.post(self._settings.get(['api_server']) + '/api/printer/monitor',
                                  json=self._printer_state, headers=headers)

                if r is not None and r.status_code == 200:
                    rb = r.json()
                    self._logger.debug('Message: %s' % self._printer_state)

                    # Message acknowledged
                    if 'status' in rb and rb['status'] == 'ok':
                        self._logger.info('Message acknowledged')
                        return

                # Message syntax correct but validation errors
                elif r.status_code == 422:
                    self._logger.error('Invalid message : ' + str(r.json()))
                    return

                # Message syntax correct but validation errors
                elif r.status_code == 429:
                    self._logger.error(str(r.json()['message']))
                    return

            except Exception as ex:
                self._logger.exception('Caught an exception ' + str(ex))
                pass

            time.sleep(sleep)

        self._logger.debug('Unable to send the message')

    def __get_current_printer_state(self):
        """
        Establishes the current state of the printer

        :returns: void
        """

        try:
            self._printer_state['state'] = self._printer.get_state_id().lower()
        except (KeyError, ValueError) as ex:
            self._logger.error(str(ex))
            self._printer_state['state'] = self.STATE_UNKNOWN

    def __get_current_temperatures(self):
        """
        Establishes the current temperatures (extruder and heatbed) of the
        printer

        :returns: void
        """

        self._printer_state['heatbed_temperature'] = {}
        self._printer_state['extruder_temperature'] = {}

        self._printer_state['heatbed_temperature']['current'] = 0
        self._printer_state['heatbed_temperature']['target'] = 0
        self._printer_state['extruder_temperature']['current'] = 0
        self._printer_state['extruder_temperature']['target'] = 0

        try:
            temperatures = self._printer.get_current_temperatures()

            # ~ Retrieve the heatbed temperatures
            if 'bed' in temperatures:
                heatbedtemperature_current = temperatures['bed']['actual']
                self._printer_state['heatbed_temperature']['current'] = int(
                    heatbedtemperature_current) if heatbedtemperature_current is not None else 0

                heatbedtemperature_target = temperatures['bed']['target']
                self._printer_state['heatbed_temperature']['target'] = int(
                    heatbedtemperature_target) if heatbedtemperature_target is not None else 0

            # ~ Retrieve the extruder temperatures
            if 'tool0' in temperatures:
                extrudertemperature_current = temperatures['tool0']['actual']
                self._printer_state['extruder_temperature']['current'] = int(
                    extrudertemperature_current) if extrudertemperature_current is not None else 0
                extrudertemperature_target = temperatures['tool0']['target']
                self._printer_state['extruder_temperature']['target'] = int(
                    extrudertemperature_target) if extrudertemperature_target is not None else 0

        except (KeyError, ValueError) as ex:
            self._logger.error(str(ex))

    def __get_printjob_state(self):
        """
        Establishes the state of the current printjob

        :returns: void
        """
        try:
            # ~ Determine the progression of the printjob
            current_data = self._printer.get_current_data()

            progress = current_data['progress']['completion']
            self._printer_state['printjob']['progress'] = int(
                progress) if progress is not None else 0

            print_time_left = current_data['progress']['printTimeLeft']
            self._printer_state['printjob']['time_remaining'] = print_time_left if print_time_left is not None else 0

            print_time_elapsed = current_data['progress']['printTime']
            self._printer_state['printjob'][
                'time_elapsed'] = print_time_elapsed if print_time_elapsed is not None else 0

            # ~ Determine the filename of the printjob
            printjob = self._printer.get_current_job()
            if printjob['file']['name'] is not None:
                self._printer_state['printjob']['filename'] = printjob['file']['name']
            else:
                self._printer_state['printjob']['filename'] = self.STATE_UNKNOWN

        except (KeyError, ValueError) as ex:
            self._logger.error(str(ex))
            self._printer_state['printjob']['progress'] = 0
            self._printer_state['printjob']['time_remaining'] = 0
            self._printer_state['printjob']['filename'] = self.STATE_UNKNOWN

    def __get_printjob_statistics(self, payload):
        """
        Retrieves the statistics of the current printjob.

        :param payload: the payload as provided with the associated event
        :returns: void
        """
        try:
            # ~ Retrieve some statistics from the metadata
            file_data = self._file_manager.get_metadata(
                payload['origin'], payload['file'])

            if 'analysis' in file_data:
                if 'filament' in file_data['analysis']:
                    if 'tool0' in file_data['analysis']['filament']:
                        filament_length = file_data['analysis']['filament']['tool0']['length']
                        self._printer_state['printjob'][
                            'filament_length'] = filament_length if filament_length is not None else 0
            else:
                self._printer_state['printjob']['filament_length'] = 0

            self._printer_state['printjob']['time_elapsed'] = payload['time']
        except (KeyError, ValueError) as ex:
            self._logger.error(str(ex))

    def Shutdown(self, payload):
        """
        Updates the printer state upon shutdown of OctoPrint.

        :param payload: the payload as provided with the event
        :returns: void
        """

        self._printer_state['state'] = self.STATE_OFFLINE

        self._logger.debug('Shutdown : %s' % str(payload))

    def Disconnected(self, payload):
        """
        Updates the printer state when disconnected.

        :param payload: the payload as provided with the event
        :returns: void
        """

        self._printer_state['state'] = self.STATE_OFFLINE

        self._logger.debug('Disconnected : %s' % str(payload))

    def Connected(self, payload):
        """
        Updates the printer state when connected.

        :param payload: the payload as provided with the event
        :returns: void
        """

        self.__get_current_printer_state()
        self.__get_current_temperatures()

        self._logger.debug('Connected : %s' % str(payload))

    def PrintStarted(self, payload):
        """
        Updates the printer state when a printjob has been started.

        :param payload: the payload as provided with the event
        :returns: void
        """
        self.__get_current_printer_state()
        self.__get_current_temperatures()
        self.__get_printjob_state()
        self._printer_state['printjob']['started_at'] = datetime.utcnow().isoformat()
        self._printer_state['printjob']['status'] = self.JOB_STATUS_IN_PROGRESS

        self._logger.debug('PrintStarted : %s' % str(payload))

    def PrintFailed(self, payload):
        """
        Updates the printer state when a printjob has failed (or cancelled).

        :param payload: the payload as provided with the event
        :returns: void
        """

        self.__get_current_printer_state()
        self.__get_printjob_statistics(payload)
        self._printer_state['printjob']['status'] = self.JOB_STATUS_FAILED

        self._logger.debug('PrintFailed : %s' % str(payload))

    def PrintDone(self, payload):
        """
        Updates the printer state when a printjob has been completed.

        :param payload: the payload as provided with the event
        :returns: void
        """

        self.__get_printjob_statistics(payload)
        self.__get_current_printer_state()
        self._printer_state['printjob']['status'] = self.JOB_STATUS_SUCCESS

        self._logger.debug('PrintDone : %s' % str(payload))

    def PrintPaused(self, payload):
        """
        Updates the printer state when a printjob has been paused.

        :param payload: the payload as provided with the event
        :returns: void
        """

        self.__get_current_printer_state()

        self._logger.debug('PrintPaused : %s' % str(payload))

    def PrintResumed(self, payload):
        """
        Updates the printer state when a printjob has been resumed.

        :param payload: the payload as provided with the event
        :returns: void
        """

        self.__get_current_printer_state()

        self._logger.debug('PrintResumed : %s' % str(payload))

    def Waiting(self, payload):
        """
        Updates the printer state when a printjob has been paused.
        In this case a GCode command commands was sent to the printer through
        OctoPrint.

        :param payload: the payload as provided with the event
        :returns: void
        """

        self.PrintPaused(payload)

    def on_after_startup(self):
        """
        Send first notification after startup of OctoPrint. This will initialize
        the printer state parameters if that's not been taken care of yet.

        :returns: void
        """
        self.__notify_event()

    def on_startup(self, host, port):
        """
        Keep the port number this OctoPrint instance is running on

        :param host: the name of the host on which this OctoPrint instance is running
        :param port: the port on which this OctoPrint instance is running
        :returns: void
        """

        self._port = port

    def on_event(self, event, payload):
        """
        Handles the processing of a fired event by the OctoPrint instance.

        :param event: the type of event that got fired
        :param payload: the payload as provided with the event
        :returns: void
        """

        if payload is None:
            payload = {}

        try:
            # This check is necessary since some events are tuple
            if isinstance(event, str) and hasattr(self, event):
                self._logger.debug('Event fired: %s ' % str(event))

                getattr(self, event)(payload)
                self.__notify_event()

        except AttributeError as ex:
            self._logger.exception('Caught an exception ' + str(ex))
            return

    def on_print_progress(self, storage, path, progress):
        """
        Handles the processing of the event when 1% of a running print job has
        been completed.

        :param storage: location of the file
        :param path: path of the file
        :param progress: current progress as a value between 0 and 100
        :returns: void
        """

        self._logger.debug('Print Progress: %s ' % str(progress))
        self.__get_printjob_state()
        self.__get_current_temperatures()
        self.__notify_event()

    def on_settings_save(self, data):
        octoprint.plugin.SettingsPlugin.on_settings_save(self, data)
        self._verified = False

    def get_settings_defaults(self):
        return dict(
            api_server='http://volta.azuya.studio',
            api_token='Volta API Token',
            retry=1,
            time_retry=2,
        )

    def get_assets(self):
        return dict()

    def get_template_configs(self):
        return [
            dict(type='settings', custom_bindings=False)
        ]

    def get_template_vars(self):
        return dict()

    def get_update_information(self):
        return dict(
            Volta=dict(
                displayName='Volta',
                displayVersion=self._plugin_version,
                type='github_release',
                user='azuyalabs',
                repo='OctoPrint-Volta',
                current=self._plugin_version,
                pip='https://github.com/azuyalabs/OctoPrint-Volta/archive/{target_version}.zip'
            )
        )


__plugin_name__ = 'Volta'


def __plugin_load__():
    global __plugin_implementation__
    __plugin_implementation__ = VoltaPlugin()

    global __plugin_hooks__
    __plugin_hooks__ = {
        'octoprint.plugin.softwareupdate.check_config': __plugin_implementation__.get_update_information
    }

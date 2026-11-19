# Modified for the MRS100 fork of ha-meross-local-broker (2026-11-13).
# Upstream: https://github.com/albertogeniola/ha-meross-local-broker
# Licensed under the Apache License, Version 2.0. See NOTICE.
# Modifications copyright 2026 the MRS100 fork contributors.

import argparse
import json
import logging
import re
import ssl
import time
import uuid
from datetime import datetime, timedelta
from threading import RLock, Thread
from typing import Dict, List, Optional

import paho.mqtt.client as mqtt
from expiringdict import ExpiringDict
from meross_iot.model.enums import OnlineStatus

from broker_bridge import BrokerDeviceBridge
from database import init_db
from db_helper import dbhelper
from logger import get_logger, set_logger_level
from model.db_models import Device
import mqtt_integrity
from protocol import _build_mqtt_message
from timezone_utils import build_time_payload, build_time_rules, needs_time_sync

CLIENT_ID = 'broker_agent'
APPLIANCE_MESSAGE_TOPICS = '/appliance/+/publish'
APPLIANCE_SUBSCRIBE_TOPIC = '/appliance/+/subscribe'
NAT_TOPIC = '/_nat_/#'
DISCONNECTION_TOPIC = '$SYS/client-disconnections'
AGENT_TOPIC = '/_agent'

l = get_logger(__name__)

APPLIANCE_PUBLISH_TOPIC_RE = re.compile("/appliance/([a-zA-Z0-9]+)/publish")
APPLIANCE_SUBSCRIBE_TOPIC_RE = re.compile("/appliance/([a-zA-Z0-9]+)/subscribe")
DISCONNECTION_TOPIC_RE = re.compile(r"^\$SYS/client-disconnections$")
_NAT_RE = re.compile(r"/_nat_/([a-zA-Z0-9\-]+)")
_CLIENTID_RE = re.compile('^fmware:([a-zA-Z0-9]+)_[a-zA-Z0-9]+$')
_DEVICE_UPDATE_CACHE_INTERVAL_SECONDS = 60
# How often the agent polls Appliance.System.All from devices with stale info (devices reconnecting after a
# broker restart publish nothing on their own, so this is what keeps their status and timezone in sync)
_DEVICE_REFRESH_INTERVAL_SECONDS = 60
# Minimum interval between two Appliance.System.Time pushes to the same device (avoids loops if a device refuses it)
_TIMEZONE_SYNC_COOLDOWN_SECONDS = 600

# MRS100 / roller-shutter support. The official cloud persists signalOpen /
# signalClose and re-applies them to the device; the local broker emulates it.
_ROLLER_SHUTTER_CONFIG_NS = 'Appliance.RollerShutter.Config'
_ROLLER_SHUTTER_STATE_NS = 'Appliance.RollerShutter.State'
_ROLLER_SHUTTER_POSITION_NS = 'Appliance.RollerShutter.Position'
_ROLLER_SHUTTER_ADJUST_NS = 'Appliance.RollerShutter.Adjust'
_ROLLER_SHUTTER_TYPES = {'mrs100', 'mss560', 'mss570', 'mrs200'}
_COVER_CONFIG_REAPPLY_COOLDOWN_SECONDS = 300


def parse_args():
    parser = argparse.ArgumentParser(description='MQTT Broker Agent')
    parser.add_argument('--port', type=int, help='MQTT server port', default=2001)
    parser.add_argument('--host', type=str, help='MQTT server hostname', default='localhost')
    parser.add_argument('--username', type=str, required=True, help='MQTT username')
    parser.add_argument('--password', type=str, required=True, help='MQTT password')
    parser.add_argument('--debug', dest='debug', action='store_true', help='When set, prints debug messages')
    parser.add_argument('--cert-ca', required=True, type=str, help='Path to the root CA certificate path')
    parser.add_argument('--timezone', type=str, default=None,
                        help='IANA timezone (e.g. Europe/Rome) pushed to devices that report none. Disabled when omitted.')
    parser.set_defaults(debug=False)
    parser.set_defaults(enable_bridging=False)
    return parser.parse_args()


def guess_subdevice_type(subdevices_data: Dict):
    if 'mts100v3' in subdevices_data:
        return 'mts100v3'
    elif 'ms100' in subdevices_data:
        return 'ms100'
    else:
        l.warning('Could not identify subdevice type from subdevice data: %s', str(subdevices_data))
        return 'unknown'


class Broker:
    def __init__(self,
                 hostname: str,
                 port: int,
                 username: str,
                 password: str,
                 cert_ca: str,
                 enable_bridging: bool,
                 device_timezone: Optional[str] = None):
        self.hostname = hostname
        self.port = port
        self.username = username
        self.password = password
        self.cert_ca = cert_ca
        self.bridging_enabled = enable_bridging
        self.device_timezone = self._validate_timezone(device_timezone)
        self._timezone_sync_attempts = {}
        self.c = mqtt.Client(client_id="broker", clean_session=True, protocol=mqtt.MQTTv311, transport="tcp")
        self.c.username_pw_set(username=self.username, password=self.password)

        context = ssl.create_default_context(cafile=self.cert_ca)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_REQUIRED
        self.c.tls_set_context(context)

        self.c.on_connect = self._on_connect
        self.c.on_disconnect = self._on_disconnect
        self.c.on_message = self._on_message
        self.c.on_subscribe = self._on_subscribe
        self._lock = RLock()
        self._devices_sys_info_timestamp = {}
        self._cover_config_reapply_ts = {}
        self._bridges = {}

        self._nat_table = ExpiringDict(max_age_seconds=30, max_len=50000)

    def setup(self, max_wait: float = 60):
        """Connect to Mosquitto, waiting for it to accept TLS connections.

        The previous approach probed the port with a raw TCP connect and closed
        it immediately, which made Mosquitto log "unexpected eof while
        reading" at every startup. Retrying the real TLS connection avoids
        that spurious error.
        """
        l.debug("Connecting MQTT client as %s", self.username)
        deadline = time.time() + max_wait
        while True:
            try:
                self.c.connect(host=self.hostname, port=self.port)
                return
            except OSError as ex:
                if time.time() >= deadline:
                    raise
                l.info("MQTT broker not ready yet (%s), retrying", ex)
                time.sleep(1)

    def _on_connect(self, client, userdata, rc, other):
        l.debug("Connected to broker, rc=%s", str(rc))
        self.c.subscribe(
            [(NAT_TOPIC, 2), (APPLIANCE_MESSAGE_TOPICS, 2), (DISCONNECTION_TOPIC, 2), (APPLIANCE_SUBSCRIBE_TOPIC, 2),
             (AGENT_TOPIC, 2)])

    def _on_subscribe(self, client, userdata, mid, granted_qos):
        l.debug("Subscribed to relevant topics")
        l.info("Re-loading connected device status.")
        self._issue_devices_discovery()
        self.process_pending_unbinds()

    def _on_message(self, client, userdata, msg):
        l.debug("Local MQTT: received message on topic %s", msg.topic)
        self._handle_message(topic=msg.topic, payload=msg.payload)

    def _on_disconnect(self, client, userdata, rc):
        l.debug("Disconnection detected. Reason: %s" % str(rc))
        # If the client disconnected explicitly
        if rc == mqtt.MQTT_ERR_SUCCESS:
            pass
        else:
            # Otherwise, if the disconnection was not intentional, we probably had a connection drop.
            l.warning("Client has been disconnected. Connection will be re-attempted.")

    def setdown(self):
        l.info("Disconnecting from mqtt broker")
        self.c.disconnect()
        l.debug("Stopping the MQTT looper.")
        self.c.loop_stop(True)
        l.info("MQTT Client has fully disconnected.")

    def _issue_devices_discovery(self) -> None:
        devices = dbhelper.get_all_devices()
        for d in devices:
            self._issue_device_get_all(device_uuid=d.uuid)

    def _issue_device_get_all(self, device_uuid: str) -> None:
        device = dbhelper.get_device_by_uuid(device_uuid=device_uuid)
        msg, message_id = _build_mqtt_message(method="GET",
                                              namespace="Appliance.System.All",
                                              payload={},
                                              dev_key=device.owner_user.mqtt_key)
        self.c.publish(topic=f"/appliance/{device_uuid}/subscribe", payload=msg)

    def refresh_stale_devices(self) -> List[str]:
        """Issue Appliance.System.All to every known device whose info is missing or older than the cache interval."""
        now = datetime.now()
        refreshed = []
        for device in dbhelper.get_all_devices():
            last_update_ts = self._devices_sys_info_timestamp.get(device.uuid)
            if last_update_ts is None or (now - last_update_ts).total_seconds() > _DEVICE_UPDATE_CACHE_INTERVAL_SECONDS:
                self._issue_device_get_all(device.uuid)
                refreshed.append(device.uuid)
        return refreshed

    def process_pending_unbinds(self) -> List[str]:
        """Announce removed devices so clients drop them instead of keeping ghosts.

        meross_iot only releases a device on an Appliance.Control.Unbind push;
        deleting it from the broker database alone leaves the HA entities behind.
        """
        published = []
        with self._lock:
            # Read the primitive values first: deleting a row commits, which
            # expires the ORM instances and makes later attribute reads raise
            # ObjectDeletedError.
            pending = [(row.device_uuid, row.user_id)
                       for row in dbhelper.get_pending_unbinds()]
            for device_uuid, user_id in pending:
                user = dbhelper.get_user_by_id(user_id)
                if user is None:
                    dbhelper.delete_pending_unbind(device_uuid)
                    continue
                msg, _ = _build_mqtt_message(
                    method="PUSH",
                    namespace="Appliance.Control.Unbind",
                    payload={},
                    dev_key=user.mqtt_key,
                    header_from=f"/appliance/{device_uuid}/publish")
                self.c.publish(topic=f"/app/{user.user_id}/subscribe",
                               payload=msg)
                dbhelper.delete_pending_unbind(device_uuid)
                l.info("Published unbind for device %s", device_uuid)
                published.append(device_uuid)
        return published

    def start_periodic_refresh(self, interval_seconds: int = _DEVICE_REFRESH_INTERVAL_SECONDS) -> Thread:
        def _loop():
            while True:
                time.sleep(interval_seconds)
                try:
                    self.refresh_stale_devices()
                    self.process_pending_unbinds()
                except Exception:
                    l.exception("Periodic device refresh failed")

        thread = Thread(target=_loop, name="device-refresh", daemon=True)
        thread.start()
        return thread

    def _handle_device_publication(self, device_uuid: str, topic: str, payload: dict):
        # If the message comes from a known device, update its online status
        dbhelper.update_device_status(device_uuid=device_uuid, status=OnlineStatus.ONLINE)

        user = dbhelper.find_user_owner_by_device_uuid(device_uuid)
        if user is None:
            l.warning("No user associated to device UUID %s, message will be skipped.", device_uuid)
            return

        # If this is the first time we see this device or if its cached info is old, update its channel status
        last_update_ts = self._devices_sys_info_timestamp.get(device_uuid)
        if last_update_ts is None or (datetime.now() - last_update_ts).seconds > _DEVICE_UPDATE_CACHE_INTERVAL_SECONDS:
            l.info("Update required for device %s Issuing SystemAll command to discover its channels "
                   "and supplementary data", device_uuid)
            self._issue_device_get_all(device_uuid)

        # For subdevices, we need to intercept BIND and UNBIND events as they are the only messages that carry the
        # subdevice_type information.
        # If the event is a Hub Bind/Unbind event, handle it accordingly
        if payload.get('header', {}).get('namespace', {}) == 'Appliance.Hub.Bind':
            for d in payload.get('payload').get('bind'):
                dbhelper.bind_subdevice(subdevice_type=d.get('deviceType'),
                                        subdevice_id=d.get('id'),
                                        hub_uuid=device_uuid)

        if payload.get('header', {}).get('namespace', {}) == 'Appliance.Hub.Unbind':
            for d in payload.get('payload').get('bind'):
                dbhelper.unbind_subdevice(subdevice_id=d.get('id'))

        # Some devices require the broker to acknowledge their binding message in order to complete the process.
        if payload.get('header', {}).get('namespace', {}) == 'Appliance.Control.Bind' \
            and payload.get('header', {}).get('method', {}) == 'SET':
            bind_ack, message_id = _build_mqtt_message(method='SETACK', namespace='Appliance.Control.Bind', header_from='/cloud/hook/subscribe', payload={}, dev_key=user.mqtt_key)
            self.c.publish(topic=f"/appliance/{device_uuid}/subscribe", payload=bind_ack)

        # Cache the ability document. Besides being useful metadata for the app,
        # it lets us create the roller-shutter channel before System.All arrives.
        namespace = payload.get('header', {}).get('namespace', {})
        method = payload.get('header', {}).get('method', {})
        if namespace == 'Appliance.System.Ability' and method == 'GETACK':
            body = payload.get('payload', {}) or {}
            ability = body.get('ability', body)
            if isinstance(ability, dict):
                set_ability = getattr(dbhelper, 'set_device_ability', None)
                if set_ability is not None:
                    set_ability(device_uuid=device_uuid, ability=ability)
                if _ROLLER_SHUTTER_STATE_NS in ability:
                    dbhelper.update_device_channel(device_uuid=device_uuid, channel_id=0)

        # Cache cover state/calibration reported by the device. Adjustment is a
        # report/result, not a desired config; it is never replayed.
        if namespace in (_ROLLER_SHUTTER_POSITION_NS, _ROLLER_SHUTTER_STATE_NS) \
                and method in ('GETACK', 'PUSH'):
            set_status = getattr(dbhelper, 'set_roller_shutter_status', None)
            if set_status is not None:
                set_status(device_uuid=device_uuid, payload=payload.get('payload', {}) or {})
        elif namespace == _ROLLER_SHUTTER_ADJUST_NS and method in ('GETACK', 'PUSH'):
            set_adjust = getattr(dbhelper, 'set_roller_shutter_adjust', None)
            if set_adjust is not None:
                set_adjust(device_uuid=device_uuid, payload=payload.get('payload', {}) or {})

        # Forward the device push notification to the app channel
        l.debug("Local MQTT -> Local MQTT: forwarding push notification received from device %s to user %s",
                device_uuid, user)
        self.c.publish(topic=f"/app/{user.user_id}/subscribe", payload=json.dumps(payload))

        # In case there is a bridged remote connection, forward the event to the remote broker as well
        if self.bridging_enabled:
            self._forward_message_to_remote(bridge_uuid=device_uuid, topic=topic,
                                            payload=json.dumps(payload).encode("utf8"))

    @staticmethod
    def _validate_timezone(tz_name: Optional[str]) -> Optional[str]:
        if not tz_name:
            l.info("No device timezone configured: devices will not receive Appliance.System.Time")
            return None
        try:
            build_time_rules(tz_name, start_ts=int(time.time()), years=1)
        except ValueError:
            l.error("Unknown timezone '%s': device time sync disabled", tz_name)
            return None
        return tz_name

    def _sync_device_timezone(self, device_uuid: str, device_time: Optional[dict], dev_key: str) -> bool:
        """Push the configured timezone (with DST rules) to a device reporting a missing/different one.

        The Meross cloud does this on every connection; power-metering devices keep reporting zero
        electricity/consumption values until they receive it. Returns True when a message was published.
        """
        if not needs_time_sync(device_time, self.device_timezone):
            return False
        now = time.time()
        last_attempt = self._timezone_sync_attempts.get(device_uuid)
        if last_attempt is not None and now - last_attempt < _TIMEZONE_SYNC_COOLDOWN_SECONDS:
            l.debug("Timezone sync for device %s attempted recently, skipping", device_uuid)
            return False
        reported = (device_time or {}).get('timezone')
        l.info("Device %s reports timezone %r, pushing %s", device_uuid, reported, self.device_timezone)
        msg, _ = _build_mqtt_message(method="SET",
                                              namespace="Appliance.System.Time",
                                              payload=build_time_payload(self.device_timezone, now_ts=int(now)),
                                              dev_key=dev_key)
        self.c.publish(topic=f"/appliance/{device_uuid}/subscribe", payload=msg)
        self._timezone_sync_attempts[device_uuid] = now
        return True

    def _handle_message_to_agent(self, topic: str, payload: dict) -> None:
        # Try to guess the channels from the system_all payload
        namespace = payload.get('header', {}).get('namespace', None)
        method = payload.get('header', {}).get('method', None)
        from_appliance = payload.get('header', {}).get('from', None)

        if namespace == 'Appliance.System.All' and method == 'GETACK':
            # Retrieve appliance uuid
            match = APPLIANCE_PUBLISH_TOPIC_RE.fullmatch(from_appliance)
            appliance_uuid = match.group(1)

            # Retrieve system_all info
            system = payload.get('payload', {}).get('all', {}).get('system', None)
            if system is None:
                l.warning("Missing or invalid payload Appliance.System.All payload: could not find system attribute")
                return

            # Update device info
            hardware = system.get('hardware')
            firmware = system.get('firmware')
            device_time = system.get('time')
            device = dbhelper.get_device_by_uuid(device_uuid=appliance_uuid)
            device.device_type = hardware.get('type')
            device.sub_type = hardware.get('subType')
            device.hdware_version = hardware.get('version')
            device.fmware_version = firmware.get('version')
            device.domain = f"{firmware.get('server')}:{firmware.get('port')}"
            # Receiving this publication proves the device is connected to the
            # broker. Do not copy system.online.status: firmware can report 0
            # when it is not bound to the Meross cloud, which would mark a
            # perfectly reachable local device offline in the HTTP device list.
            device.online_status = OnlineStatus.ONLINE
            device.local_ip = firmware.get('innerIp')
            dbhelper.update_device(device)

            # Like the Meross cloud, make sure the device knows its timezone (needed for power metering)
            self._sync_device_timezone(appliance_uuid, device_time, device.owner_user.mqtt_key)

            digest = payload.get('payload', {}).get('all', {}).get('digest', None)
            if digest is None:
                l.warning("Missing or invalid payload Appliance.System.All payload: could not find digest attribute")
            else:
                hub_data = digest.get("hub")
                if hub_data is not None:
                    subdevices_data = hub_data.get('subdevice', [])
                    self._update_hub_subdevices(hub_device=device, subdevices_data=subdevices_data)

                # Guess channels and Store Appliance info on DB
                togglex_switches = digest.get('togglex')
                roller_switches = (digest.get('rollershutter') or digest.get('rollerShutter')
                                   or digest.get('cover') or digest.get('rollerShutterState'))
                if isinstance(roller_switches, dict):
                    roller_switches = [roller_switches]

                # Guess by togglex
                if togglex_switches is not None and len(togglex_switches) > 0:
                    l.debug("Guessing channels via togglex")
                    for d in togglex_switches:
                        channel_id = d.get('channel')
                        dbhelper.update_device_channel(device_uuid=appliance_uuid, channel_id=channel_id)
                elif roller_switches:
                    l.debug("Guessing roller-shutter channels from System.All digest")
                    for d in roller_switches:
                        if isinstance(d, dict):
                            channel_id = int(d.get('channel', 0) or 0)
                        else:
                            channel_id = 0
                        dbhelper.update_device_channel(device_uuid=appliance_uuid, channel_id=channel_id)
                elif (device.device_type or '').lower() in _ROLLER_SHUTTER_TYPES:
                    # MRS100 and siblings are roller shutters even when their
                    # System.All digest carries no explicit channel list.
                    dbhelper.update_device_channel(device_uuid=appliance_uuid, channel_id=0)
                else:
                    l.warning("Could not guess the channels for device uuid %s", appliance_uuid)

            # Update the last update timestamp
            ts = datetime.now()
            l.info("Setting last update timestamp to %s for device %s", ts, appliance_uuid)
            self._devices_sys_info_timestamp[device.uuid] = ts

            # Emulate the cloud-side persistence of roller shutter timing.
            self._reapply_roller_shutter_config(appliance_uuid)

            if self.bridging_enabled:
                self._get_or_create_bridge(device_uuid=device.uuid)

        elif namespace == 'Appliance.System.Time' and method == 'SETACK':
            match = APPLIANCE_PUBLISH_TOPIC_RE.fullmatch(from_appliance or '')
            l.info("Device %s acknowledged the timezone update", match.group(1) if match else from_appliance)

    def _handle_device_disconnected(self, payload: dict) -> None:
        if payload.get("event") != "disconnect":
            l.warning("Invalid or unhandled event received: %s", payload.get("event"))
            return
        data = payload.get("data")
        client_id = data.get("client_id")
        username = data.get("username")
        address = data.get("address")
        reason = data.get("reason")
        l.debug("Broker reported client %s (username: %s, ip: %s) disconnected for reason %s", client_id, username,
                address, str(reason))

        # Only proceed if the client-id belongs to a hw device
        device_match = _CLIENTID_RE.fullmatch(client_id)
        if device_match:
            uuid = device_match.group(1)
            if dbhelper.get_device_by_uuid(device_uuid=uuid) is None:
                # The device was forgotten while its MQTT session was open.
                l.info("Device %s disconnected after being forgotten", uuid)
            else:
                dbhelper.update_device_status(
                    device_uuid=uuid, status=OnlineStatus.OFFLINE)
                l.info("Device %s has disconnected from broker", uuid)

            # Clear last timestamp update
            if uuid in self._devices_sys_info_timestamp:
                del self._devices_sys_info_timestamp[uuid]
            self._cover_config_reapply_ts.pop(uuid, None)

            # Stop the corresponding bridge
            bridge = self._bridges.get(uuid)
            if bridge is not None:
                l.debug("Stopping and Removing device MQTT-Bridge: %s", uuid)
                bridge.stop()
                del self._bridges[uuid]
            else:
                l.debug("No MQTT Bridge found for device %s, nothing to stop.", uuid)

    def _handle_app_to_device_message(self, device_uuid: str, payload: dict) -> None:
        """Observe commands that the app/HA publishes to a device.

        The MRS100 stores little or no roller-shutter timing itself: the
        official cloud re-applies signalOpen/signalClose. We persist the
        desired config here and replay it after System.All/reconnect.
        """
        header = payload.get('header', {}) or {}
        if header.get('from') == '/_agent':
            return
        if header.get('namespace') != _ROLLER_SHUTTER_CONFIG_NS:
            return
        if header.get('method') != 'SET':
            return
        set_config = getattr(dbhelper, 'set_roller_shutter_config', None)
        if set_config is None:
            return
        config = (payload.get('payload', {}) or {}).get('config')
        if isinstance(config, dict):
            set_config(device_uuid=device_uuid, config=config)
        elif isinstance(config, list):
            for entry in config:
                if isinstance(entry, dict):
                    set_config(device_uuid=device_uuid, config=entry)

    def _reapply_roller_shutter_config(self, device_uuid: str) -> None:
        """Replay persisted roller-shutter timing to the device, rate-limited."""
        find_user = getattr(dbhelper, 'find_user_owner_by_device_uuid', None)
        get_configs = getattr(dbhelper, 'get_roller_shutter_configs', None)
        if find_user is None or get_configs is None:
            return
        user = find_user(device_uuid)
        if user is None:
            return
        rows = get_configs(device_uuid)
        if not rows:
            return
        now = time.time()
        if now - self._cover_config_reapply_ts.get(device_uuid, 0) < _COVER_CONFIG_REAPPLY_COOLDOWN_SECONDS:
            return
        for row in rows:
            try:
                config = json.loads(row.payload_json)
            except Exception:
                config = {'channel': row.channel,
                          'signalOpen': row.signal_open,
                          'signalClose': row.signal_close}
            msg, _ = _build_mqtt_message(
                method='SET', namespace=_ROLLER_SHUTTER_CONFIG_NS,
                payload={'config': config}, dev_key=user.mqtt_key,
                header_from='/_agent')
            self.c.publish(topic=f"/appliance/{device_uuid}/subscribe", payload=msg)
            l.info("Re-applied roller-shutter config to device %s channel %s",
                   device_uuid, config.get('channel', row.channel))
        self._cover_config_reapply_ts[device_uuid] = now

    def _check_device_message_integrity(self, device_uuid: str, payload: dict) -> bool:
        if mqtt_integrity.MODE == "off":
            return True
        owner = dbhelper.find_user_owner_by_device_uuid(device_uuid)
        if owner is None:
            ok, reason = False, "unknown_device"
        else:
            ok, reason = mqtt_integrity.evaluate(device_uuid, payload, owner.mqtt_key)
        if ok:
            return True
        if mqtt_integrity.should_log(device_uuid, reason):
            l.warning("MQTT integrity check failed for device %s (%s, mode=%s)",
                      device_uuid, reason, mqtt_integrity.MODE)
        return not mqtt_integrity.enforced()

    def _handle_message(self, topic: str, payload: bytes):
        try:
            # Handling DISCONNECTION control messages
            disconnection_match = DISCONNECTION_TOPIC_RE.match(topic)
            if disconnection_match is not None:
                p = json.loads(payload)
                self._handle_device_disconnected(payload=p)
                return

            # Handling NATTED messages if bridging is enabled
            if self.bridging_enabled:
                match = _NAT_RE.fullmatch(topic)
                if match is not None:
                    nat_table_index = match.group(1)
                    nat_entry = self._nat_table.get(nat_table_index)
                    if nat_entry is None:
                        l.error("Invalid _NAT_ address received. Message will be discarded.")
                        return
                    original_topic = nat_entry.get("original_from_attribute")
                    originating_bridge_uuid = nat_entry.get("originating_bridge_uuid")
                    #p = json.loads(payload)
                    #p['header']['from'] = original_topic
                    #original_payload = json.dumps(p).encode('utf8')
                    self._forward_message_to_remote(topic=original_topic, payload=payload,
                                                    bridge_uuid=originating_bridge_uuid)
                    return

            # App/HA -> device commands. The agent already subscribes to this
            # topic; observe roller-shutter config without interfering.
            sub_match = APPLIANCE_SUBSCRIBE_TOPIC_RE.fullmatch(topic)
            if sub_match is not None:
                p = json.loads(payload)
                self._handle_app_to_device_message(device_uuid=sub_match.group(1), payload=p)
                return

            # Handling messages pushed to APPLIANCE publication topics
            match = APPLIANCE_PUBLISH_TOPIC_RE.fullmatch(topic)
            if match is not None:
                device_uuid = match.group(1)
                p = json.loads(payload)
                if not self._check_device_message_integrity(device_uuid, p):
                    return
                self._handle_device_publication(device_uuid=device_uuid, topic=topic, payload=p)
                return

            # Handling messages pushed to /_agent dedicated topic
            if topic == AGENT_TOPIC:
                p = json.loads(payload)
                from_device = (p.get('header') or {}).get('from')
                origin_match = APPLIANCE_PUBLISH_TOPIC_RE.fullmatch(from_device or '')
                if origin_match is not None and not self._check_device_message_integrity(
                        origin_match.group(1), p):
                    return
                self._handle_message_to_agent(topic=topic, payload=p)
                return

        except Exception as ex:
            l.exception("An error occurred while handling a message received on topic %s", str(topic))

    def _get_or_create_bridge(self, device_uuid: str) -> BrokerDeviceBridge:
        bridge: BrokerDeviceBridge = self._bridges.get(device_uuid)
        if bridge is None:
            l.info("Creating MQTT bridge for device %s", device_uuid)
            # Retrieve device info
            device = dbhelper.get_device_by_uuid(device_uuid=device_uuid)
            bridge = BrokerDeviceBridge(broker=self,
                                        device_uuid=device_uuid,
                                        device_client_id=device.client_id,
                                        meross_device_mac=device.mac,
                                        meross_user_id=str(device.user_id),
                                        meross_key=device.owner_user.mqtt_key)
            bridge.start()
            self._bridges[device_uuid] = bridge
        return bridge

    def forward_device_command_locally(self, topic: str, payload: bytes, originating_bridge_uuid: str):
        # When a device receives a command from Meross Cloud, we need to forward it to the local broker.
        # In order to send back the ACK to that command, we apply masquerading NAT, so that we can later
        # intercept the responses to such messages and forward them to the remote broker
        with self._lock:
            message_data = json.loads(payload)
            from_attribute = message_data.get('header', {}).get('from', None)

            # Generate nat entry and store the original "address" into the nat table
            rand_uuid = str(uuid.uuid4())
            nat_entry = f"/_nat_/{rand_uuid}"
            self._nat_table[rand_uuid] = {
                "original_from_attribute": from_attribute,
                "originating_bridge_uuid": originating_bridge_uuid
            }

            # Replace the original address with the natted one and submit the message locally
            message_data['header']['from'] = nat_entry
            newdata = json.dumps(message_data).encode('utf8')
            l.debug("Device Bridge (%s) -> Local MQTT, topic: %s, message: %s", originating_bridge_uuid, str(topic),
                    str(newdata))
            self.c.publish(topic=topic, payload=newdata)

    def _forward_message_to_remote(self, topic: str, payload: bytearray, bridge_uuid: str):
        bridge = self._get_or_create_bridge(device_uuid=bridge_uuid)
        if bridge is not None:
            bridge.send_message(topic=topic, payload=payload)
        else:
            l.debug("Bridge creation failed for device %s", bridge_uuid)

    def _update_hub_subdevices(self, hub_device: Device, subdevices_data: List[Dict]) -> None:
        l.debug("Updating subdevices for hub %s (%s)", hub_device.uuid, hub_device.dev_name)
        # Add newly discovered subdevices
        for d in subdevices_data:
            subdevice_id = d.get('id')
            subdevice_type = guess_subdevice_type(d)
            subdevice = dbhelper.get_subdevice_by_id(subdevice_id)
            if subdevice is None:
                l.info("Found new subdevice %s belonging to hub %s (%s)", subdevice_id, hub_device.uuid,
                       hub_device.dev_name)
                subdevice = dbhelper.bind_subdevice(subdevice_type=subdevice_type, subdevice_id=subdevice_id,
                                                    hub_uuid=hub_device.uuid)
            if (subdevice.sub_device_type is None or subdevice.sub_device_type == 'unknown') and subdevice_type is not None:
                l.warning("Subdevice %s was of unknown, but from update data looks like an %s."
                          "From now on, this subdevice is treated as an %s.", subdevice_id,
                          subdevice_type, subdevice_type)
                subdevice.sub_device_type = subdevice_type
                dbhelper.update_subdevice(subdevice)

        # Remove old subdevices that were not listed any longer
        current_devices_ids = {x.get('id') for x in subdevices_data}
        for d in hub_device.child_subdevices:
            if d.sub_device_id not in current_devices_ids:
                l.warning("Removing subdevice %s from hub %s (%s)", d.sub_device_id, hub_device.uuid,
                          hub_device.dev_name)
                dbhelper.unbind_subdevice(subdevice_id=d.sub_device_id)


def main():
    # Parse Args
    args = parse_args()
    if args.debug:
        set_logger_level(logging.DEBUG)

    # Init or setup DB
    init_db()

    # Online statuses are reset in cont-init before mosquitto starts. Resetting
    # here would erase the ONLINE status that devices set while authenticating
    # during the add-on startup.

    # This fork is local-only. Ignore any legacy enable_meross_link value
    # that may remain in an existing database.
    b = Broker(hostname=args.host,
               port=args.port,
               username=args.username,
               password=args.password,
               cert_ca=args.cert_ca,
               enable_bridging=False,
               device_timezone=args.timezone)
    b.start_periodic_refresh()

    reconnect_interval = 10  # [seconds]
    while True:
        try:
            b.setup()

            while True:
                b.c.loop(timeout=60, max_packets=-1)
                b.c.loop_forever()

        except KeyboardInterrupt as ex:
            l.warning("Keyboard interrupt received, exiting.")
            b.setdown()
            break
        except Exception as ex:
            l.exception("An unhandled error occurred")
            b.setdown()
            time.sleep(reconnect_interval)


if __name__ == '__main__':
    main()

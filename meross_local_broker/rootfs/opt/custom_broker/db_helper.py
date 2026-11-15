# Modified for the MRS100 fork of ha-meross-local-broker (2026-11-13).
# Upstream: https://github.com/albertogeniola/ha-meross-local-broker
# Licensed under the Apache License, Version 2.0. See NOTICE.
# Modifications copyright 2026 the MRS100 fork contributors.

from meross_iot.model.enums import OnlineStatus
from logger import get_logger
from typing import Optional, List, Dict
from constants import BASE62_ALPHABET
from database import db_session
from model.db_models import (UserToken, Device, User, DeviceChannel, SubDevice,
                             Event, Configuration, RollerShutterConfig, DeviceAbility,
                             RollerShutterStatus, RollerShutterAdjust)
from datetime import datetime
from utilities import _hash_password
from model.enums import BridgeStatus, EventType
from datetime import datetime
import json
import random


l = get_logger(__name__)


class DbHelper:
    def __init__(self):
        self._s = db_session

    def add_update_user(self, email: str, password: str, user_key: str, user_id: int) -> User:
        # `password` is the clear password. The local account is a singleton, so
        # changing its login must update the existing row instead of inserting a
        # duplicate user_id.
        u = self._s.query(User).filter(User.email == email).first()
        if u is None and user_id is not None:
            u = self._s.query(User).filter(User.user_id == user_id).first()
        if u is None:
            l.info(f"User %s not found in db. Adding a new entry...", email)
            if user_key is None:
                # Prefer using an empty KEY rather than a randomized one
                user_key = ''
            salt = ''.join(random.choice(BASE62_ALPHABET) for i in range(16))
            hashed_pass = _hash_password(salt=salt, password=password, pre_apply_md5=True)
            u = User(email=email, user_id=user_id, salt=salt, password=hashed_pass, mqtt_key=user_key)
            self._s.add(u)
            self._s.commit()
        else:
            l.warning(f"User %s already exists. Updating its password/email...", email)
            salt = u.salt
            hashed_pass = _hash_password(salt=salt, password=password, pre_apply_md5=True)
            u.email = email
            u.password = hashed_pass
            u.password_upgraded = True
            # Keep the existing key so already-paired devices stay authenticated.
            if not u.mqtt_key and user_key:
                u.mqtt_key = user_key

            self._s.add(u)
            self._s.commit()
        return u

    def store_new_user_token(self, userid, token) -> UserToken:
        token = UserToken(user_id=userid, token=token)
        self._s.add(token)
        self._s.commit()
        return token

    def associate_user_device(self, userid: int, mac: str, uuid: str, device_client_id: str) -> None:
        # Check if a device with that MAC already exists. If so, update its user_id.
        # If not, create a new one
        d = self._s.query(Device).filter(Device.mac == mac).first()
        if d is None:
            d = Device(mac=mac)
        d.user_id = userid
        d.uuid = uuid
        d.client_id = device_client_id
        self._s.add(d)
        self._s.commit()

    def get_user_by_email(self, email: str) -> Optional[User]:
        return self._s.query(User).filter(User.email == email).first()

    def remove_user_token(self, token: str) -> None:
        token = self._s.query(UserToken).get(token)
        if token is not None:
            self._s.delete(token)
            self._s.commit()

    def get_user_by_id(self, userid: int) -> Optional[User]:
        return self._s.query(User).filter(User.user_id == userid).first()

    def get_user_by_token(self, token: str) -> Optional[User]:
        ut = self._s.query(UserToken).filter(UserToken.token == token).first()
        if ut is None:
            return None
        return ut.user

    def find_user_owner_by_device_uuid(self, device_uuid: str) -> Optional[User]:
        dev = self._s.query(Device).filter(Device.uuid == device_uuid).first()
        if dev is None:
            return None
        return dev.owner_user

    def get_device_by_uuid(self, device_uuid: str) -> Optional[Device]:
        dev = self._s.query(Device).filter(Device.uuid == device_uuid).first()
        if dev is None:
            return None
        return dev

    def update_device(self, device: Device) -> Device:
        self._s.add(device)
        self._s.commit()
        return device

    def get_all_devices(self) -> List[Device]:
        return self._s.query(Device).all()

    def update_device_status(self, device_uuid: str, status: OnlineStatus) -> None:
        dev = self._s.query(Device).filter(Device.uuid == device_uuid).first()
        if dev is None:
            raise Exception("Device %s was not present into the database." % device_uuid)
        dev.online_status = status
        dev.last_seen_time = datetime.now()
        self._s.add(dev)
        self._s.commit()

    def update_device_channel(self, device_uuid: str, channel_id: int) -> DeviceChannel:
        dev = self._s.query(Device).filter(Device.uuid == device_uuid).first()
        if dev is None:
            raise Exception("Device %s was not present into the database." % device_uuid)

        channel = None
        for c in dev.channels:
            if c.channel_id == channel_id:
                l.debug("Channel %d already attached to device uuid %s: channel__id %s", channel_id, device_uuid,
                        c.device_channel_id)
                channel = c
                break

        # TODO: channel name/type update?

        if channel is None:
            l.info("Discovered channel index %d on device uuid %s", channel_id, device_uuid)
            channel = DeviceChannel()
            channel.channel_id = channel_id
            channel.device_uuid = device_uuid

            self._s.add(channel)
            self._s.commit()

        return channel

    def update_device_bridge_status(self, device_uuid: str, status: BridgeStatus):
        device = self.get_device_by_uuid(device_uuid=device_uuid)
        if device is None:
            raise Exception("Invalid device uuid")
        device.bridge_status = status
        self._s.add(device)
        self._s.commit()

    def bind_subdevice(self, subdevice_type: str, subdevice_id: str, hub_uuid: str) -> SubDevice:
        l.info("Binding subdevice %s to hub id %s", subdevice_id, hub_uuid)
        # Check if the subdevice exists. If so, update the existing one
        subdevice = self._s.query(SubDevice).filter(SubDevice.sub_device_id == subdevice_id).first()
        if subdevice is None:
            subdevice = SubDevice(subdevice_id=subdevice_id)
        subdevice.sub_device_type = subdevice_type
        subdevice.hub_uuid = hub_uuid
        self._s.add(subdevice)
        self._s.commit()
        return subdevice

    def unbind_subdevice(self, subdevice_id: str) -> None:
        l.info("Unbinding subdevice %s", subdevice_id)
        # Check if the subdevice exists. If so, update the existing one
        subdevice = self._s.query(SubDevice).filter(SubDevice.sub_device_id == subdevice_id).first()
        if subdevice is not None:
            self._s.delete(subdevice)
            self._s.commit()

    def get_all_subdevices(self) -> List[SubDevice]:
        return self._s.query(SubDevice).all()

    def get_subdevice_by_id(self, subdevice_id: str) -> Optional[SubDevice]:
        return self._s.query(SubDevice).filter(SubDevice.sub_device_id == subdevice_id).first()

    def update_subdevice(self, subdevice: SubDevice) -> SubDevice:
        self._s.add(subdevice)
        self._s.commit()
        return subdevice

    def reset_device_online_status(self) -> None:
        self._s.query(Device).update({Device.online_status: OnlineStatus.UNKNOWN})
        self._s.commit()

    def store_event(self, event_type: EventType, device_uuid: str = None, sub_device_id: str = None, user_id:str = None, details: str = None) -> Event:
        event = Event(event_type=event_type, device_uuid=device_uuid, sub_device_id=sub_device_id, user_id=user_id, details=details)
        self._s.add(event)
        self._s.commit()
        return event

    def set_roller_shutter_config(self, device_uuid: str, config: Dict) -> RollerShutterConfig:
        """Upsert one channel of roller-shutter timing config.

        `config` is the object found in Appliance.RollerShutter.Config payloads
        (channel, signalOpen, signalClose, and possibly extra fields). Values
        are stored in milliseconds, matching the Meross protocol.
        """
        channel = int(config.get('channel', 0) or 0)
        row = self._s.query(RollerShutterConfig).filter(
            RollerShutterConfig.device_uuid == device_uuid,
            RollerShutterConfig.channel == channel).first()
        if row is None:
            row = RollerShutterConfig(device_uuid=device_uuid, channel=channel)
        row.signal_open = config.get('signalOpen')
        row.signal_close = config.get('signalClose')
        row.payload_json = json.dumps(config)
        row.updated_at = datetime.now()
        self._s.add(row)
        self._s.commit()
        l.info("Stored roller-shutter config for device %s channel %s: %s",
               device_uuid, channel, row.payload_json)
        return row

    def get_roller_shutter_configs(self, device_uuid: str) -> List[RollerShutterConfig]:
        return self._s.query(RollerShutterConfig).filter(
            RollerShutterConfig.device_uuid == device_uuid).all()

    def set_device_ability(self, device_uuid: str, ability: Dict) -> DeviceAbility:
        row = self._s.query(DeviceAbility).filter(
            DeviceAbility.device_uuid == device_uuid).first()
        if row is None:
            row = DeviceAbility(device_uuid=device_uuid)
        row.ability_json = json.dumps(ability)
        row.updated_at = datetime.now()
        self._s.add(row)
        self._s.commit()
        return row

    def get_device_ability(self, device_uuid: str) -> Optional[DeviceAbility]:
        return self._s.query(DeviceAbility).filter(
            DeviceAbility.device_uuid == device_uuid).first()

    @staticmethod
    def _cover_entries(payload: Dict, keys) -> List[Dict]:
        entries = []
        if isinstance(payload, dict):
            for key in keys:
                data = payload.get(key)
                if isinstance(data, dict):
                    entries.append(data)
                elif isinstance(data, list):
                    entries.extend(d for d in data if isinstance(d, dict))
            if not entries and 'channel' in payload:
                entries.append(payload)
        elif isinstance(payload, list):
            entries.extend(d for d in payload if isinstance(d, dict))
        return entries

    def set_roller_shutter_status(self, device_uuid: str, payload: Dict) -> int:
        """Upsert position/state from Appliance.RollerShutter.Position/State."""
        entries = self._cover_entries(payload, ('position', 'state', 'cover'))
        for entry in entries:
            channel = int(entry.get('channel', 0) or 0)
            row = self._s.query(RollerShutterStatus).filter(
                RollerShutterStatus.device_uuid == device_uuid,
                RollerShutterStatus.channel == channel).first()
            if row is None:
                row = RollerShutterStatus(device_uuid=device_uuid, channel=channel)
            if 'position' in entry:
                row.position = entry.get('position')
            if 'state' in entry:
                row.state = entry.get('state')
            row.updated_at = datetime.now()
            self._s.add(row)
        self._s.commit()
        return len(entries)

    def get_roller_shutter_statuses(self, device_uuid: str) -> List[RollerShutterStatus]:
        return self._s.query(RollerShutterStatus).filter(
            RollerShutterStatus.device_uuid == device_uuid).all()

    def set_roller_shutter_adjust(self, device_uuid: str, payload: Dict) -> int:
        """Upsert calibration results from Appliance.RollerShutter.Adjust."""
        entries = self._cover_entries(payload, ('adjust', 'adjust_results'))
        for entry in entries:
            channel = int(entry.get('channel', 0) or 0)
            row = self._s.query(RollerShutterAdjust).filter(
                RollerShutterAdjust.device_uuid == device_uuid,
                RollerShutterAdjust.channel == channel).first()
            if row is None:
                row = RollerShutterAdjust(device_uuid=device_uuid, channel=channel)
            row.payload_json = json.dumps(entry)
            row.updated_at = datetime.now()
            self._s.add(row)
        self._s.commit()
        return len(entries)

    def get_roller_shutter_adjusts(self, device_uuid: str) -> List[RollerShutterAdjust]:
        return self._s.query(RollerShutterAdjust).filter(
            RollerShutterAdjust.device_uuid == device_uuid).all()

    def get_configuration(self) -> Optional[Configuration]:
        """ Return the current configuration """
        q = self._s.query(Configuration).filter(Configuration.configuration_id==0).first()
        return q

    def add_update_configuration(self, enable_meross_link:bool, local_user_id:str) -> Configuration:
        q: Configuration = self._s.query(Configuration).filter(Configuration.configuration_id==0).first()
        if (q is None):
            q = Configuration(configuration_id=0)
        q.enable_meross_link = enable_meross_link
        q.local_account_id = local_user_id
        self._s.add(q)
        self._s.commit()

    def get_events(self, limit: int = 50, event_type: EventType = None, device_uuid: str = None, sub_device_id: str = None, user_id:str = None, from_timestamp: datetime = None, to_timestamp: datetime = None) -> List[Event]:
        """ Searches for events based on the inputed parameters """
        q = self._s.query(Event)
        if event_type is not None:
            q = q.filter(Event.event_type == event_type)
        if device_uuid is not None:
            q = q.filter(Event.device_uuid == device_uuid)
        if sub_device_id is not None:
            q = q.filter(Event.sub_device_id == sub_device_id)
        if user_id is not None:
            q = q.filter(Event.user_id == user_id)
        if from_timestamp is not None:
            q = q.filter(Event.timestamp >= from_timestamp)
        if to_timestamp is not None:
            q = q.filter(Event.timestamp <= to_timestamp)
        return q.order_by(Event.event_id.desc()).limit(limit).all()

dbhelper = DbHelper()

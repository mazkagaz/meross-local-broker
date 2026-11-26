# Modified for the MRS100 fork of ha-meross-local-broker (2026-11-13).
# Upstream: https://github.com/albertogeniola/ha-meross-local-broker
# Licensed under the Apache License, Version 2.0. See NOTICE.
# Modifications copyright 2026 the MRS100 fork contributors.

from datetime import datetime
from email.policy import default
from optparse import Option
from typing import Dict, Optional

from compat import OnlineStatus
from sqlalchemy import Column, String, BigInteger, Integer, Boolean, Text
from sqlalchemy import ForeignKey, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base
from sqlalchemy.inspection import inspect
from time_utils import UTCDateTime, utcnow


from model.enums import BridgeStatus, EventType


class Serializer(object):

    def serialize(self):
        return {Serializer.to_camel_case(c): getattr(self, c) for c in inspect(self).attrs.keys()}

    @staticmethod
    def to_camel_case(snake_str) -> str:
        #return snake_str
        components = snake_str.split('_')
        return components[0] + ''.join(x.title() for x in components[1:])

    @staticmethod
    def serialize_list(l):
        return [m.serialize() for m in l]


class User(Base, Serializer):
    __tablename__ = 'users'
    __table_args__ = {'sqlite_autoincrement': True}

    user_id = Column(Integer, primary_key=True)
    email = Column(String(64), unique=True, autoincrement=True)
    salt = Column(String(64))
    password = Column(String(255))
    mqtt_key = Column(String(64))
    owned_devices = relationship("Device", back_populates="owner_user")
    password_upgraded = Column(Boolean, default=True)

    def __init__(self, email: str, salt: str, password: str, mqtt_key: str, user_id: Optional[int], *args, **kwargs):
        self.email = email
        self.salt = salt
        self.password = password
        self.mqtt_key = mqtt_key
        self.user_id = user_id

    def __repr__(self):
        return '<User %r (%r)>' % (self.user_id, self.email)

    def serialize(self, ):
        d = Serializer.serialize(self)
        del d['password']
        del d['salt']
        del d['ownedDevices']
        return d


class UserToken(Base, Serializer):
    __tablename__ = 'user_tokens'

    token_hash = Column(String(64), primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id'))
    user = relationship("User")
    created_at = Column(UTCDateTime, default=utcnow, nullable=False)
    last_used_at = Column(UTCDateTime, default=utcnow, nullable=False)
    absolute_expires_at = Column(UTCDateTime, nullable=False)

    def __init__(self, token_hash: str, user_id: int, created_at: datetime,
                 last_used_at: datetime, absolute_expires_at: datetime, *args, **kwargs):
        self.token_hash = token_hash
        self.user_id = user_id
        self.created_at = created_at
        self.last_used_at = last_used_at
        self.absolute_expires_at = absolute_expires_at

    def __repr__(self):
        return '<UserToken user=%r>' % (self.user_id,)

    def serialize(self):
        d = Serializer.serialize(self)
        del d['user']
        del d['tokenHash']
        return d


class DeviceChannel(Base, Serializer):
    __tablename__ = 'channels'
    __table_args__ = {'sqlite_autoincrement': True}

    device_channel_id = Column(Integer, primary_key=True, autoincrement=True)
    device_uuid = Column(String, ForeignKey('devices.uuid'))
    channel_id = Column(Integer)
    device = relationship("Device", back_populates="channels")

    def serialize(self):
        d = Serializer.serialize(self)
        del d['device']
        return d


class Device(Base, Serializer):
    __tablename__ = 'devices'

    mac = Column(String(16), primary_key=True)
    uuid = Column(String(36), unique=True)
    online_status = Column(Enum(OnlineStatus))
    dev_name = Column(String(255))
    dev_icon_id = Column(String(255))
    bind_time = Column(BigInteger())
    device_type = Column(String(255))
    sub_type = Column(String(255))
    channels = relationship("DeviceChannel", back_populates="device")
    region = Column(String(255))
    fmware_version = Column(String(16))
    hdware_version = Column(String(16))
    user_dev_icon = Column(String(64))
    icon_type = Column(String(64))
    skill_number = Column(String(64))
    domain = Column(String(255))
    reserved_domain = Column(String(255))

    local_ip = Column(String(16))
    client_id = Column(String(255))

    user_id = Column(String, ForeignKey('users.user_id'))
    owner_user = relationship("User", back_populates="owned_devices")
    child_subdevices = relationship("SubDevice", back_populates="parent_device")

    # Technical fields
    last_seen_time = Column(UTCDateTime)
    bridge_status = Column(Enum(BridgeStatus), default=BridgeStatus.DISCONNECTED)

    def __init__(self, mac: str, *args, **kwargs):
        self.mac = mac

    def serialize(self):
        d = Serializer.serialize(self)
        del d['ownerUser']
        d['onlineStatus'] = (self.online_status.value
                             if self.online_status is not None
                             else OnlineStatus.UNKNOWN.value)
        d['userEmail'] = self.owner_user.email
        d['channels'] = DeviceChannel.serialize_list(self.channels)
        d['childSubdevices'] = SubDevice.serialize_list(self.child_subdevices)
        d['bridgeStatus'] = self.bridge_status.name
        # meross_iot warns for None/string bind times and ignores the value.
        d['bindTime'] = int(self.bind_time) if self.bind_time is not None else 0
        return d


class RevokedDevice(Base, Serializer):
    """MACs explicitly forgotten by their owner.

    A forgotten device keeps its broker credentials, so its next MQTT login is
    refused until a new pairing claims it again.
    """
    __tablename__ = 'revoked_devices'

    mac = Column(String(16), primary_key=True)
    revoked_at = Column(UTCDateTime, default=utcnow)


class SubDevice(Base, Serializer):
    __tablename__ = 'subdevices'

    sub_device_id = Column(String(16), primary_key=True)
    true_id = Column(String(8))
    sub_device_type = Column(String(16))
    sub_device_vendor = Column(String(16))
    sub_device_name = Column(String(255))
    sub_device_icon_id = Column(String(16))

    hub_uuid = Column(String, ForeignKey('devices.uuid'))
    parent_device = relationship("Device", back_populates="child_subdevices")

    def __init__(self, subdevice_id: str, *args, **kwargs):
        self.sub_device_id = subdevice_id

    def serialize(self):
        d = Serializer.serialize(self)
        del d['parentDevice']
        return d


class RollerShutterConfig(Base, Serializer):
    """Desired roller-shutter timing config, persisted by the broker.

    The official cloud persists signalOpen/signalClose and re-applies them to
    MRS100-class devices; the local broker must do the same or the device can
    fall back to its default timing after reconnects.
    """
    __tablename__ = 'roller_shutter_configs'

    config_id = Column(Integer, primary_key=True, autoincrement=True)
    device_uuid = Column(String, ForeignKey('devices.uuid'))
    channel = Column(Integer, default=0)
    signal_open = Column(Integer, nullable=True)
    signal_close = Column(Integer, nullable=True)
    payload_json = Column(Text)
    updated_at = Column(UTCDateTime)


class DeviceAbility(Base, Serializer):
    """Last Appliance.System.Ability document seen for a device."""
    __tablename__ = 'device_abilities'

    device_uuid = Column(String, ForeignKey('devices.uuid'), primary_key=True)
    ability_json = Column(Text)
    updated_at = Column(UTCDateTime)


class PendingUnbind(Base, Serializer):
    """Device unbound by the user; the agent publishes the Unbind push."""
    __tablename__ = 'pending_unbinds'

    device_uuid = Column(String, primary_key=True)
    user_id = Column(Integer, nullable=False)
    created_at = Column(UTCDateTime)


class RollerShutterStatus(Base, Serializer):
    """Last reported roller-shutter position/state per channel."""
    __tablename__ = 'roller_shutter_status'

    status_id = Column(Integer, primary_key=True, autoincrement=True)
    device_uuid = Column(String, ForeignKey('devices.uuid'))
    channel = Column(Integer, default=0)
    position = Column(Integer, nullable=True)
    state = Column(Integer, nullable=True)
    updated_at = Column(UTCDateTime)


class RollerShutterAdjust(Base, Serializer):
    """Last Appliance.RollerShutter.Adjust document per channel.

    The document carries calibration results (adjusted, open/close times,
    direction, control mode, autoAdjust, ...). It is exposed through devList
    and kept for diagnostics; it is not replayed as a config, because Adjust
    SET is an operational/calibration command.
    """
    __tablename__ = 'roller_shutter_adjust'

    adjust_id = Column(Integer, primary_key=True, autoincrement=True)
    device_uuid = Column(String, ForeignKey('devices.uuid'))
    channel = Column(Integer, default=0)
    payload_json = Column(Text)
    updated_at = Column(UTCDateTime)


class Event(Base, Serializer):
    __tablename__ = 'events'
    __table_args__ = {'sqlite_autoincrement': True}
    
    event_id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(UTCDateTime, default=utcnow, server_default=func.now())
    event_type = Column(Enum(EventType), nullable=False)
    device_uuid = Column(String, nullable=True)
    sub_device_id = Column(String, nullable=True)
    user_id = Column(String, nullable=True)
    details = Column(String, nullable=True)

    def serialize(self):
        d = Serializer.serialize(self)
        d['eventType'] = self.event_type.value
        return d


class Configuration(Base, Serializer):
    __tablename__ = 'configuration'
    configuration_id = Column(Integer, primary_key=True)
    enable_meross_link = Column(Boolean, default=False)
    local_account_id = Column(String, ForeignKey('users.user_id'))
    local_account = relationship("User")

    def serialize(self):
        d = Serializer.serialize(self)
        del d['localAccount']
        del d['localAccountId']
        d['email'] = self.local_account.email
        return d
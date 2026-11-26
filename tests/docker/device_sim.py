"""Minimal MRS100 MQTT device simulator for the Docker end-to-end test.

Connects to the real broker as a paired device, answers Ability/All/roller
shutter GETs and applies Position/Config/Adjust SETs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import string
import time

import paho.mqtt.client as mqtt

STATE = "Appliance.RollerShutter.State"
POSITION = "Appliance.RollerShutter.Position"
CONFIG = "Appliance.RollerShutter.Config"
ADJUST = "Appliance.RollerShutter.Adjust"


def _md5(value: str) -> str:
    return hashlib.md5(value.encode("utf8")).hexdigest()


class Simulator:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.position = 0
        self.state = 0
        self.signal_open = 45000
        self.signal_close = 50000
        self.adjust = 0
        self.client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"fmware:{args.uuid}_1",
        )
        password = f"{args.user_id}_{_md5(args.mac + args.key)}"
        self.client.username_pw_set(args.mac, password)
        self.client.tls_set(ca_certs=args.ca)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

    @property
    def publish_topic(self) -> str:
        return f"/appliance/{self.args.uuid}/publish"

    @property
    def subscribe_topic(self) -> str:
        return f"/appliance/{self.args.uuid}/subscribe"

    def _message(self, namespace: str, method: str, payload: dict) -> bytes:
        message_id = _md5("".join(random.choice(string.ascii_uppercase + string.digits)
                                 for _ in range(16)))
        timestamp = int(time.time())
        sign = _md5(f"{message_id}{self.args.key}{timestamp}")
        return json.dumps({
            "header": {
                "from": self.publish_topic,
                "messageId": message_id,
                "method": method,
                "namespace": namespace,
                "payloadVersion": 1,
                "sign": sign,
                "timestamp": timestamp,
                "triggerSrc": "Device",
            },
            "payload": payload,
        }).encode("utf8")

    def _publish(self, namespace: str, method: str, payload: dict,
                 agent: bool = False) -> None:
        topic = "/_agent" if agent else self.publish_topic
        self.client.publish(topic, self._message(namespace, method, payload))

    def _body(self, namespace: str) -> dict:
        if namespace == "Appliance.System.Ability":
            return {"ability": {
                "Appliance.System.All": {},
                "Appliance.System.Ability": {},
                "Appliance.System.Time": {},
                "Appliance.Control.Multiple": {},
                STATE: {},
                POSITION: {},
                CONFIG: {},
                ADJUST: {},
            }}
        if namespace == "Appliance.System.All":
            return {"all": {
                "system": {
                    "hardware": {
                        "type": "mrs100", "subType": "un", "version": "7.0.0",
                        "uuid": self.args.uuid, "macAddress": self.args.mac,
                    },
                    "firmware": {"version": "7.3.3"},
                    "online": {"status": 1},
                },
                "digest": {"togglex": [{"channel": 0, "onoff": 1}]},
            }}
        if namespace == "Appliance.System.Time":
            return {"time": [{"channel": 0, "timestamp": int(time.time()),
                              "timezone": "UTC"}]}
        if namespace == POSITION:
            return {"position": [{"channel": 0, "position": self.position}]}
        if namespace == STATE:
            return {"state": [{"channel": 0, "state": self.state,
                               "timestamp": int(time.time()), "stoppedBy": 0}]}
        if namespace == CONFIG:
            return {"config": [{"channel": 0, "signalOpen": self.signal_open,
                                "signalClose": self.signal_close,
                                "autoAdjust": 1}]}
        if namespace == ADJUST:
            return {"adjust": [{"channel": 0, "value": 0,
                                "status": self.adjust}]}
        return {}

    def _apply_set(self, namespace: str, payload: dict) -> None:
        if namespace == POSITION:
            channel = (payload.get("position") or [{}])[0]
            position = channel.get("position")
            if position is not None:
                position = int(position)
                if position == -1:
                    self.state = 0
                else:
                    self.position = position
                    self.state = 1 if position > 0 else 2
        elif namespace == CONFIG:
            channel = (payload.get("config") or [{}])[0]
            if "signalOpen" in channel:
                self.signal_open = int(channel["signalOpen"])
            if "signalClose" in channel:
                self.signal_close = int(channel["signalClose"])
        elif namespace == ADJUST:
            channel = (payload.get("adjust") or [{}])[0]
            self.adjust = int(channel.get("value") or 0)

    def _on_connect(self, client, userdata, flags, reason_code, properties) -> None:
        print(f"device connected: {reason_code}", flush=True)
        if reason_code.is_failure:
            raise SystemExit(1)
        client.subscribe(self.subscribe_topic)
        self._publish("Appliance.System.All", "GETACK",
                      self._body("Appliance.System.All"), agent=True)
        self._publish("Appliance.System.Ability", "GETACK",
                      self._body("Appliance.System.Ability"), agent=True)

    def _on_message(self, client, userdata, message) -> None:
        try:
            envelope = json.loads(message.payload)
            header = envelope.get("header") or {}
            namespace = header.get("namespace")
            method = header.get("method")
            payload = envelope.get("payload") or {}
        except (ValueError, AttributeError):
            return
        if not namespace:
            return

        print(f"{method} {namespace}", flush=True)
        sender = header.get("from", "")
        response_to_agent = sender.startswith("/_agent")
        if namespace == "Appliance.Control.Multiple":
            responses = []
            for item in payload.get("multiple") or []:
                item_header = item.get("header") or {}
                item_ns = item_header.get("namespace")
                responses.append({
                    "header": {"namespace": item_ns, "method": "GETACK"},
                    "payload": self._body(item_ns),
                })
            self._publish(namespace, "SETACK", {"multiple": responses},
                          agent=response_to_agent)
            return

        if method == "SET":
            self._apply_set(namespace, payload)
            self._publish(namespace, "SETACK", self._body(namespace),
                          agent=response_to_agent)
            if namespace == POSITION:
                self._publish(STATE, "PUSH", self._body(STATE))
            return

        self._publish(namespace, "GETACK", self._body(namespace),
                      agent=response_to_agent)

    def run(self) -> None:
        self.client.connect(self.args.host, self.args.port, keepalive=60)
        self.client.loop_forever()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2001)
    parser.add_argument("--ca", required=True)
    parser.add_argument("--mac", default="AA:BB:CC:DD:EE:01")
    parser.add_argument("--uuid", default="90000000000000000000000000000001")
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--key", required=True)
    args = parser.parse_args()
    Simulator(args).run()


if __name__ == "__main__":
    main()

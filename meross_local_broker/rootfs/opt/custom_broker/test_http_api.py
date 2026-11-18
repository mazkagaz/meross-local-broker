"""API compatibility checks. Run with: python3 -m unittest test_http_api."""
import base64
from datetime import datetime, timedelta
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class HttpApiCompatibilityTest(unittest.TestCase):
    INGRESS = {'X-Ingress-Path': '/api/hassio_ingress/test'}

    @classmethod
    def setUpClass(cls):
        # Rebind before importing the API, whose import initializes the database.
        # Never open or modify the configured /data database during these tests.
        import database
        from sqlalchemy import create_engine

        temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(temporary.cleanup)
        engine = create_engine(f"sqlite:///{Path(temporary.name) / 'api.db'}")
        cls.addClassCleanup(engine.dispose)
        original_bind = database.db_session.session_factory.kw['bind']
        database.db_session.remove()
        database.db_session.configure(bind=engine)
        cls.addClassCleanup(database.db_session.configure, bind=original_bind)
        cls.addClassCleanup(database.db_session.remove)
        engine_patch = patch.object(database, 'engine', engine)
        engine_patch.start()
        cls.addClassCleanup(engine_patch.stop)

        import http_api
        cls.app = http_api.app
        cls.database = database

    def setUp(self):
        self.database.db_session.remove()
        self.database.Base.metadata.drop_all(bind=self.database.engine)
        self.database.init_db()
        from db_helper import dbhelper
        self.user = dbhelper.add_update_user(
            email='test@example.com', password='test-password',
            user_id=1, user_key='0123456789abcdef0123456789abcdef')
        self.user_id = str(self.user.user_id)
        self.mqtt_key = self.user.mqtt_key
        self.client = self.app.test_client()
        from rate_limit import login_rate_limiter
        login_rate_limiter.reset()

    def tearDown(self):
        from rate_limit import login_rate_limiter
        login_rate_limiter.reset()
        self.database.db_session.remove()

    @staticmethod
    def envelope(payload):
        from constants import _SECRET
        params = base64.b64encode(json.dumps(payload).encode()).decode()
        timestamp, nonce = '1788750000', 'testnonce'
        signature = hashlib.md5(f'{_SECRET}{timestamp}{nonce}{params}'.encode()).hexdigest()
        return dict(params=params, timestamp=timestamp, nonce=nonce, sign=signature)

    def sign_in(self, form=False):
        envelope = self.envelope(dict(email='test@example.com', password='test-password'))
        kwargs = {'data': envelope} if form else {'json': envelope}
        return self.client.post('/v1/Auth/signIn', **kwargs)

    def test_signed_json_and_form_login_and_authenticated_request(self):
        for form in (False, True):
            with self.subTest(form=form):
                response = self.sign_in(form)
                self.assertEqual(response.status_code, 200)
                result = response.get_json()
                self.assertEqual(result['apiStatus'], 0)
                self.assertEqual(result['data']['userid'], self.user_id)
                response = self.client.post(
                    '/v1/Device/devList', json=self.envelope({}),
                    headers={'Authorization': f"Basic {result['data']['token']}"})
                self.assertEqual(response.get_json(), {'apiStatus': 0, 'info': None, 'data': []})

    def test_invalid_signature_returns_meross_error(self):
        envelope = self.envelope({})
        envelope['sign'] = 'invalid'
        response = self.client.post('/v1/Auth/signIn', data=envelope)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()['info'], 'Key verification failed')

    def test_non_object_json_returns_bad_request(self):
        response = self.client.post('/v1/Auth/signIn', json=[])
        self.assertEqual(response.status_code, 400)

    def test_numeric_timestamp_signature_is_accepted(self):
        from constants import _SECRET
        payload = {'email': 'test@example.com', 'password': 'test-password'}
        params = base64.b64encode(json.dumps(payload).encode()).decode()
        timestamp = 1788750000  # JSON number, as sent by the Android pairer.
        nonce = 'testnonce'
        signature = hashlib.md5(
            f'{_SECRET}{timestamp}{nonce}{params}'.encode()).hexdigest()
        response = self.client.post('/v1/Auth/signIn', json={
            'params': params, 'timestamp': timestamp,
            'nonce': nonce, 'sign': signature})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['apiStatus'], 0)

    def test_malformed_params_payload_returns_bad_request(self):
        from constants import _SECRET
        envelope = self.envelope({})
        envelope['params'] = 'not-base64!'
        envelope['sign'] = hashlib.md5(
            f"{_SECRET}{envelope['timestamp']}{envelope['nonce']}{envelope['params']}".encode()
        ).hexdigest()
        response = self.client.post('/v1/Auth/signIn', json=envelope)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()['info'], 'Malformed params payload')

    def test_account_password_uses_argon2id(self):
        self.assertTrue(self.user.password.startswith('$argon2id$'))
        self.assertNotIn('test-password', self.user.password)

    def test_legacy_token_table_is_replaced_without_keeping_sessions(self):
        from sqlalchemy import text
        engine = self.database.engine
        engine.execute(text('DROP TABLE user_tokens'))
        engine.execute(text('CREATE TABLE user_tokens (token VARCHAR(32) PRIMARY KEY, user_id VARCHAR)'))
        engine.execute(text("INSERT INTO user_tokens VALUES ('legacy-token', '1')"))

        self.database.init_db()

        columns = {row[1] for row in engine.execute(
            text('SELECT * FROM pragma_table_info("user_tokens")'))}
        self.assertIn('token_hash', columns)
        self.assertNotIn('token', columns)
        self.assertEqual(engine.execute(text('SELECT COUNT(*) FROM user_tokens')).scalar(), 0)

    def test_tokens_are_stored_hashed(self):
        from model.db_models import UserToken
        token = self.sign_in().get_json()['data']['token']
        self.database.db_session.remove()
        from db_helper import dbhelper
        stored = dbhelper._s.query(UserToken).first()
        self.assertIsNotNone(stored)
        self.assertNotEqual(stored.token_hash, token)
        self.assertEqual(len(stored.token_hash), 64)

    def test_idle_and_absolute_token_expiry(self):
        token = self.sign_in().get_json()['data']['token']
        headers = {'Authorization': f'Basic {token}'}

        future = datetime.utcnow() + timedelta(days=8)
        with patch('db_helper._utcnow', return_value=future):
            response = self.client.post('/v1/Device/devList', json=self.envelope({}),
                                        headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['info'], 'token_idle_expired')

        token = self.sign_in().get_json()['data']['token']
        headers = {'Authorization': f'Basic {token}'}
        future = datetime.utcnow() + timedelta(days=31)
        with patch('db_helper._utcnow', return_value=future):
            response = self.client.post('/v1/Device/devList', json=self.envelope({}),
                                        headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['info'], 'token_expired')

    def test_login_rate_limit_returns_429(self):
        for _ in range(5):
            response = self.client.post('/v1/Auth/signIn', json=self.envelope({
                'email': 'test@example.com', 'password': 'wrong-password'}))
            self.assertEqual(response.status_code, 200)
        response = self.client.post('/v1/Auth/signIn', json=self.envelope({
            'email': 'test@example.com', 'password': 'wrong-password'}))
        self.assertEqual(response.status_code, 429)
        self.assertIn('Retry-After', response.headers)

    def test_missing_token_returns_token_error(self):
        from meross_iot.http_api import ErrorCodes
        response = self.client.post('/v1/Device/devList', json=self.envelope({}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['apiStatus'], ErrorCodes.CODE_TOKEN_ERROR.value)
        self.assertEqual(response.get_json()['info'], 'token_invalid')

    def test_mqtt_app_auth_accepts_valid_and_denies_invalid_password(self):
        password = hashlib.md5(f'{self.user_id}{self.mqtt_key}'.encode()).hexdigest()
        for supplied, status, body in ((password, 200, b'ok'), ('wrong', 403, b'ko')):
            with self.subTest(status=status):
                response = self.client.post('/_devs_/auth', json={
                    'username': self.user_id, 'password': supplied, 'clientid': 'app:test'})
                self.assertEqual((response.status_code, response.data), (status, body))

    def test_invalid_mqtt_json_is_denied(self):
        for kwargs in ({'data': 'not json'}, {'json': []},
                       {'data': '{', 'content_type': 'application/json'}):
            with self.subTest(kwargs=kwargs):
                response = self.client.post('/_devs_/auth', **kwargs)
                self.assertEqual((response.status_code, response.data), (403, b'ko'))

    def test_mqtt_acl_json(self):
        from db_helper import dbhelper
        mac, uuid = 'AA:BB:CC:DD:EE:10', 'acldeviceuuid'
        dbhelper.associate_user_device(self.user.user_id, mac=mac, uuid=uuid,
                                       device_client_id='client')

        def acl(username, topic, acc, clientid):
            response = self.client.post('/_devs_/acl', json={
                'username': username, 'topic': topic, 'acc': acc,
                'clientid': clientid})
            return response.status_code, response.data

        self.assertEqual(acl(mac, f'/appliance/{uuid}/publish', 2,
                             f'fmware:{uuid}_0'), (200, b'ok'))
        self.assertEqual(acl(mac, f'/appliance/{uuid}/subscribe', 1,
                             f'fmware:{uuid}_0'), (200, b'ok'))
        # Unsubscribe checks use acc=8 and must follow the read policy.
        self.assertEqual(acl(mac, f'/appliance/{uuid}/subscribe', 8,
                             f'fmware:{uuid}_0'), (200, b'ok'))
        # Devices publish System.All/agent messages to /_agent.
        self.assertEqual(acl(mac, '/_agent', 2, f'fmware:{uuid}_0'), (200, b'ok'))
        # Devices answer commands on the app response topic; only the owner's
        # app topics are accepted.
        self.assertEqual(acl(mac, f'/app/{self.user_id}-testappid/subscribe', 2,
                             f'fmware:{uuid}_0'), (200, b'ok'))
        self.assertEqual(acl(mac, f'/app/{self.user_id}/subscribe', 2,
                             f'fmware:{uuid}_0'), (200, b'ok'))
        self.assertEqual(acl(mac, '/app/otheruser-testappid/subscribe', 2,
                             f'fmware:{uuid}_0'), (403, b'ko'))
        self.assertEqual(acl(mac, '/appliance/otheruuid/publish', 2,
                             f'fmware:{uuid}_0'), (403, b'ko'))
        self.assertEqual(acl(mac, f'/appliance/{uuid}/publish', 2,
                             'fmware:otheruuid_0'), (403, b'ko'))

        self.assertEqual(acl(self.user_id, f'/app/{self.user_id}/subscribe', 1,
                             f'app:{self.user_id}'), (200, b'ok'))
        # meross_iot also subscribes to its per-app command-response topic.
        self.assertEqual(acl(self.user_id, f'/app/{self.user_id}-testappid/subscribe', 1,
                             f'app:testappid'), (200, b'ok'))
        self.assertEqual(acl(self.user_id, '/app/otheruser-testappid/subscribe', 1,
                             'app:testappid'), (403, b'ko'))
        self.assertEqual(acl(self.user_id, f'/appliance/{uuid}/subscribe', 2,
                             f'app:{self.user_id}'), (200, b'ok'))
        self.assertEqual(acl(self.user_id, '/appliance/otheruuid/subscribe', 2,
                             f'app:{self.user_id}'), (403, b'ko'))

        self.assertEqual(acl('_agent', '/appliance/+/publish', 1, 'broker'),
                         (200, b'ok'))
        # Delivery checks use concrete topics, not the wildcard filter.
        self.assertEqual(acl('_agent', f'/appliance/{uuid}/subscribe', 1, 'broker'),
                         (200, b'ok'))
        self.assertEqual(acl('_agent', f'/appliance/{uuid}/publish', 1, 'broker'),
                         (200, b'ok'))
        self.assertEqual(acl('_agent', '/_nat_/test-id', 1, 'broker'),
                         (200, b'ok'))

    def test_admin_configuration_is_local_only(self):
        with patch('blueprints.admin.service_manager.restart_service'):
            response = self.client.put('/_admin_/configuration', json={
                'email': 'local-user',
                'password': 'local-secret',
                'enableMerossLink': True,
            }, headers=self.INGRESS)
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['email'], 'local-user')

        from db_helper import dbhelper
        self.assertFalse(dbhelper.get_configuration().enable_meross_link)
        configuration = self.client.get('/_admin_/configuration', headers=self.INGRESS).get_json()
        self.assertFalse(configuration['enableMerossLink'])

        login = self.envelope({'email': 'local-user', 'password': 'local-secret'})
        response = self.client.post('/v1/Auth/signIn', json=login)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['apiStatus'], 0)

    def test_service_log_status_classification(self):
        from s6 import ServiceInfo
        self.assertEqual(ServiceInfo.log_status_from_lines([]), 'empty')
        self.assertEqual(ServiceInfo.log_status_from_lines(['INFO: ok']), 'ok')
        self.assertEqual(ServiceInfo.log_status_from_lines(['WARNING: slow']), 'warning')
        self.assertEqual(ServiceInfo.log_status_from_lines(['ERROR: failed']), 'error')
        self.assertEqual(
            ServiceInfo.log_status_from_lines(['WARNING: slow', 'ERROR: failed']),
            'error')

    def test_devlist_returns_integer_bind_time(self):
        from db_helper import dbhelper
        dbhelper.associate_user_device(
            self.user.user_id, mac='AA:BB:CC:DD:EE:20',
            uuid='bindtimedevice', device_client_id='client')
        token = self.sign_in().get_json()['data']['token']
        response = self.client.post(
            '/v1/Device/devList', json=self.envelope({}),
            headers={'Authorization': f'Basic {token}'})
        devices = response.get_json()['data']
        self.assertEqual(len(devices), 1)
        self.assertIsInstance(devices[0]['bindTime'], int)

    def test_admin_can_forget_device(self):
        from db_helper import dbhelper
        dbhelper.associate_user_device(self.user.user_id, mac='AA:BB:CC:DD:EE:FF',
                                       uuid='test-device-uuid', device_client_id='client')
        response = self.client.delete('/_admin_/devices/test-device-uuid', headers=self.INGRESS)
        self.assertEqual(response.status_code, 204)
        self.assertIsNone(dbhelper.get_device_by_uuid('test-device-uuid'))
        self.assertTrue(dbhelper.is_device_revoked('AA:BB:CC:DD:EE:FF'))
        pending = [p for p in dbhelper.get_pending_unbinds()
                   if p.device_uuid == 'test-device-uuid']
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0].user_id, int(self.user_id))
        response = self.client.delete('/_admin_/devices/test-device-uuid', headers=self.INGRESS)
        self.assertEqual(response.status_code, 400)

    def device_login(self, mac, uuid):
        digest = hashlib.md5(f'{mac}{self.mqtt_key}'.encode()).hexdigest()
        return self.client.post('/_devs_/auth', json={
            'username': mac, 'password': f'{self.user_id}_{digest}',
            'clientid': f'fmware:{uuid}_test'})

    def test_forgotten_device_is_revoked_until_claimed(self):
        from db_helper import dbhelper
        mac, uuid = 'AA:BB:CC:DD:EE:FF', 'aabbccddeeff00112233445566778899'
        dbhelper.associate_user_device(self.user.user_id, mac=mac, uuid=uuid,
                                       device_client_id='client')
        self.assertEqual((self.device_login(mac, uuid).status_code,
                          self.device_login(mac, uuid).data), (200, b'ok'))

        token = self.sign_in().get_json()['data']['token']
        headers = {'Authorization': f'Basic {token}'}
        response = self.client.post(
            '/v1/Device/delete', json=self.envelope({'uuid': uuid}), headers=headers)
        self.assertEqual(response.get_json()['apiStatus'], 0)
        self.assertTrue(dbhelper.is_device_revoked(mac))

        # The device still holds its credentials, so the login must be refused
        # even though no user/device row points at it anymore.
        self.assertEqual(self.device_login(mac, uuid).status_code, 403)

        # Re-pairing claims the MAC again, which lifts the revocation.
        response = self.client.post(
            '/v1/Device/claim', json=self.envelope({'mac': mac}), headers=headers)
        self.assertEqual(response.get_json()['apiStatus'], 0)
        self.assertFalse(dbhelper.is_device_revoked(mac))
        relogin = self.device_login(mac, uuid)
        self.assertEqual((relogin.status_code, relogin.data), (200, b'ok'))
        # Same UUID: HA keeps the entity identity after forget/re-pair.
        self.assertIsNotNone(dbhelper.get_device_by_uuid(uuid))

    def test_authenticated_user_can_forget_owned_device(self):
        from db_helper import dbhelper
        dbhelper.associate_user_device(self.user.user_id, mac='AA:BB:CC:DD:EE:FF',
                                       uuid='owned-device', device_client_id='client')
        token = self.sign_in().get_json()['data']['token']
        response = self.client.post(
            '/v1/Device/delete', json=self.envelope({'uuid': 'owned-device'}),
            headers={'Authorization': f'Basic {token}'})
        self.assertEqual(response.get_json()['apiStatus'], 0)
        self.assertIsNone(dbhelper.get_device_by_uuid('owned-device'))
        self.assertEqual([p.device_uuid for p in dbhelper.get_pending_unbinds()],
                         ['owned-device'])

        other = dbhelper.add_update_user(
            email='other@example.com', password='other-password',
            user_id=2, user_key='ffeeddccbbaa99887766554433221100')
        dbhelper.associate_user_device(other.user_id, mac='AA:BB:CC:DD:EE:00',
                                       uuid='not-owned', device_client_id='client')
        token = self.sign_in().get_json()['data']['token']
        # The token belongs to user 1; a device owned by user 2 must be refused.
        self.assertNotEqual(2, self.user.user_id)
        response = self.client.post(
            '/v1/Device/delete', json=self.envelope({'uuid': 'not-owned'}),
            headers={'Authorization': f'Basic {token}'})
        self.assertNotEqual(response.get_json()['apiStatus'], 0)
        self.assertIsNotNone(dbhelper.get_device_by_uuid('not-owned'))
        self.assertEqual([p.device_uuid for p in dbhelper.get_pending_unbinds()],
                         ['owned-device'])

    def test_authenticated_user_can_rename_owned_device(self):
        from db_helper import dbhelper
        dbhelper.associate_user_device(self.user.user_id, mac='AA:BB:CC:DD:EE:01',
                                       uuid='rename-device-uuid', device_client_id='client')
        token = self.sign_in().get_json()['data']['token']
        headers = {'Authorization': f'Basic {token}'}

        response = self.client.post(
            '/v1/Device/name',
            json=self.envelope({'uuid': 'rename-device-uuid', 'name': '  Volet salon  '}),
            headers=headers)
        self.assertEqual(response.get_json()['apiStatus'], 0)
        self.assertEqual(dbhelper.get_device_by_uuid('rename-device-uuid').dev_name,
                         'Volet salon')

        response = self.client.post(
            '/v1/Device/name',
            json=self.envelope({'uuid': 'rename-device-uuid', 'name': '   '}),
            headers=headers)
        self.assertNotEqual(response.get_json()['apiStatus'], 0)

        # Same name on the same device is allowed; another device cannot take it.
        response = self.client.post(
            '/v1/Device/name',
            json=self.envelope({'uuid': 'rename-device-uuid', 'name': 'Volet salon'}),
            headers=headers)
        self.assertEqual(response.get_json()['apiStatus'], 0)

        dbhelper.associate_user_device(self.user.user_id, mac='AA:BB:CC:DD:EE:03',
                                       uuid='rename-device-two', device_client_id='client')
        second = dbhelper.get_device_by_uuid('rename-device-two')
        second.dev_name = 'Volet cuisine'
        dbhelper.update_device(second)

        response = self.client.post(
            '/v1/Device/name',
            json=self.envelope({'uuid': 'rename-device-uuid', 'name': 'volet cuisine'}),
            headers=headers)
        self.assertNotEqual(response.get_json()['apiStatus'], 0)
        self.assertEqual(dbhelper.get_device_by_uuid('rename-device-uuid').dev_name,
                         'Volet salon')

        # The Web UI rename path enforces the same uniqueness rule.
        from meross_iot.model.enums import OnlineStatus
        dbhelper.update_device_status('rename-device-uuid', OnlineStatus.UNKNOWN)
        response = self.client.put('/_admin_/devices/rename-device-uuid',
                                   json={'dev_name': 'Volet cuisine'}, headers=self.INGRESS)
        self.assertEqual(response.status_code, 400)
        response = self.client.put('/_admin_/devices/rename-device-uuid',
                                   json={'dev_name': 'Volet salon'}, headers=self.INGRESS)
        self.assertEqual(response.status_code, 200)

        other = dbhelper.add_update_user(
            email='rename-other@example.com', password='other-password',
            user_id=2, user_key='ffeeddccbbaa99887766554433221100')
        dbhelper.associate_user_device(other.user_id, mac='AA:BB:CC:DD:EE:02',
                                       uuid='rename-other-device', device_client_id='client')
        response = self.client.post(
            '/v1/Device/name',
            json=self.envelope({'uuid': 'rename-other-device', 'name': 'Not mine'}),
            headers=headers)
        self.assertNotEqual(response.get_json()['apiStatus'], 0)
        self.assertIsNone(dbhelper.get_device_by_uuid('rename-other-device').dev_name)

    def test_admin_is_restricted_by_nginx_and_cors_is_restricted(self):
        # nginx enforces the Supervisor-only network restriction; the backend
        # must not depend on ingress headers, which broke the panel in alpha82.
        response = self.client.get('/_admin_/devices', headers={
            'Origin': 'http://localhost'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), [])
        self.assertNotIn('Access-Control-Allow-Origin', response.headers)

        response = self.client.options('/v1/Auth/signIn', headers={
            'Origin': 'http://localhost', 'Access-Control-Request-Method': 'POST',
            'Access-Control-Request-Headers': 'Content-Type'})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('Access-Control-Allow-Origin', response.headers)

    def test_legacy_double_hashed_password_is_upgraded(self):
        from db_helper import dbhelper
        from utilities import is_argon2_hash, verify_password

        self.database.db_session.remove()
        user = dbhelper.get_user_by_email('test@example.com')
        salt = user.salt
        effective = hashlib.md5(b'test-password').hexdigest()
        user.password = hashlib.sha256(
            f"{salt}{hashlib.md5(effective.encode()).hexdigest()}".encode()).hexdigest()
        dbhelper._s.add(user)
        dbhelper._s.commit()

        response = self.sign_in()
        self.assertEqual(response.get_json()['apiStatus'], 0)

        self.database.db_session.remove()
        upgraded = dbhelper.get_user_by_email('test@example.com').password
        self.assertTrue(is_argon2_hash(upgraded))
        self.assertTrue(verify_password(upgraded, effective))

    def test_database_reinitialization_preserves_account(self):
        self.database.db_session.remove()
        self.database.engine.dispose()
        self.database.init_db()
        self.assertEqual(self.sign_in().get_json()['apiStatus'], 0)


if __name__ == '__main__':
    unittest.main()

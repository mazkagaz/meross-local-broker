"""API compatibility checks. Run with: python3 -m unittest test_http_api."""
import base64
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class HttpApiCompatibilityTest(unittest.TestCase):
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

    def tearDown(self):
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

    def test_missing_token_returns_meross_token_error(self):
        from meross_iot.http_api import ErrorCodes
        response = self.client.post('/v1/Device/devList', json=self.envelope({}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['apiStatus'], ErrorCodes.CODE_TOKEN_ERROR.value)

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
        response = self.client.post('/_devs_/acl', json={
            'username': self.user_id, 'topic': '/appliance/test/publish',
            'acc': 2, 'clientid': 'app:test'})
        self.assertEqual((response.status_code, response.data), (200, b'ok'))

    def test_admin_configuration_is_local_only(self):
        with patch('blueprints.admin.service_manager.restart_service'):
            response = self.client.put('/_admin_/configuration', json={
                'email': 'local-user',
                'password': 'local-secret',
                'enableMerossLink': True,
            })
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['email'], 'local-user')

        from db_helper import dbhelper
        self.assertFalse(dbhelper.get_configuration().enable_meross_link)
        configuration = self.client.get('/_admin_/configuration').get_json()
        self.assertFalse(configuration['enableMerossLink'])

        login = self.envelope({'email': 'local-user', 'password': 'local-secret'})
        response = self.client.post('/v1/Auth/signIn', json=login)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['apiStatus'], 0)

    def test_admin_can_forget_device(self):
        from db_helper import dbhelper
        dbhelper.associate_user_device(self.user.user_id, mac='AA:BB:CC:DD:EE:FF',
                                       uuid='test-device-uuid', device_client_id='client')
        response = self.client.delete('/_admin_/devices/test-device-uuid')
        self.assertEqual(response.status_code, 204)
        self.assertIsNone(dbhelper.get_device_by_uuid('test-device-uuid'))
        self.assertTrue(dbhelper.is_device_revoked('AA:BB:CC:DD:EE:FF'))
        response = self.client.delete('/_admin_/devices/test-device-uuid')
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
                                   json={'dev_name': 'Volet cuisine'})
        self.assertEqual(response.status_code, 400)
        response = self.client.put('/_admin_/devices/rename-device-uuid',
                                   json={'dev_name': 'Volet salon'})
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

    def test_admin_json_and_cors_preflight(self):
        response = self.client.get('/_admin_/devices', headers={'Origin': 'http://localhost'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), [])
        self.assertEqual(response.headers['Access-Control-Allow-Origin'], 'http://localhost')
        response = self.client.options('/v1/Auth/signIn', headers={
            'Origin': 'http://localhost', 'Access-Control-Request-Method': 'POST',
            'Access-Control-Request-Headers': 'Content-Type'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('POST', response.headers['Access-Control-Allow-Methods'])
        self.assertIn('Content-Type', response.headers['Access-Control-Allow-Headers'])

    def test_legacy_double_hashed_password_is_upgraded(self):
        from db_helper import dbhelper
        from utilities import _hash_password

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
        self.assertEqual(dbhelper.get_user_by_email('test@example.com').password,
                         _hash_password(salt=salt, password='test-password', pre_apply_md5=True))

    def test_database_reinitialization_preserves_account(self):
        self.database.db_session.remove()
        self.database.engine.dispose()
        self.database.init_db()
        self.assertEqual(self.sign_in().get_json()['apiStatus'], 0)


if __name__ == '__main__':
    unittest.main()

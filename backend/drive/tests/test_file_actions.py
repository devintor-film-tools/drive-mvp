import io
import tempfile
import uuid
from pathlib import Path

from django.test import Client, TestCase, override_settings

from drive import services
from drive.models import File, User
from drive.tests.test_uploads import TEST_SETTINGS


@override_settings(**TEST_SETTINGS)
class FileActionTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='drive-actions-')
        self.addCleanup(self.temp.cleanup)
        override = override_settings(DRIVE_DATA_DIR=Path(self.temp.name))
        override.enable()
        self.addCleanup(override.disable)
        self.user = User.objects.create_user('owner')
        self.other = User.objects.create_user('other')
        self.client.force_login(self.user)
        upload, _ = services.create_upload(self.user, {'name': 'before.txt', 'size_bytes': 5, 'client_key': str(uuid.uuid4())})
        services.receive_upload(self.user, upload.id, uuid.uuid4(), io.BytesIO(b'hello'))
        self.file = File.objects.get(upload=upload)
        self.url = f'/api/files/{self.file.id}'

    def change(self, **data):
        return self.client.patch(self.url, data, content_type='application/json')

    def test_rename_keeps_identity_bytes_and_quota(self):
        original = self.file
        response = self.change(name='résumé.txt', revision=1)
        self.assertEqual(response.status_code, 200)
        self.file.refresh_from_db()
        self.assertEqual(self.file.revision, 2)
        self.assertEqual(self.file.blob_key, original.blob_key)
        self.assertEqual(self.file.sha256, original.sha256)
        response = self.client.get(self.url + '/content')
        self.assertEqual(b''.join(response.streaming_content), b'hello')
        self.assertIn("filename*=utf-8''r%C3%A9sum%C3%A9.txt", response['Content-Disposition'])
        self.assertEqual(services.account_for(self.user).used_bytes, 5)

    def test_trash_restore_and_stale_retry(self):
        self.assertEqual(self.change(trashed=True, revision=1).status_code, 200)
        self.assertEqual(self.client.get('/api/files').json()['items'], [])
        trashed = self.client.get('/api/files?location=trash').json()['items']
        self.assertEqual(len(trashed), 1)
        self.assertEqual(self.client.get(self.url + '/content').status_code, 404)
        self.assertEqual(self.change(name='bad.txt', revision=2).status_code, 409)
        self.assertEqual(self.change(trashed=False, revision=2).status_code, 200)
        self.assertEqual(self.change(trashed=True, revision=1).status_code, 409)
        self.assertEqual(self.client.get('/api/files?location=trash').json()['items'], [])
        self.assertEqual(self.client.get('/api/files').json()['items'][0]['id'], str(self.file.id))
        self.assertEqual(services.account_for(self.user).used_bytes, 5)
        self.assertEqual(b''.join(self.client.get(self.url + '/content').streaming_content), b'hello')

    def test_invalid_names_and_changes_are_rejected(self):
        for name in ['', '   ', '.', '..', '../x', 'a\\b', 'x\n.txt', '\ud800', 'é' * 128]:
            self.assertEqual(self.change(name=name, revision=1).status_code, 400, repr(name))
        for data in [{'name': 'ok'}, {'trashed': 'yes', 'revision': 1}, {'name': 'ok', 'revision': True}, {'name': 'ok', 'trashed': True, 'revision': 1}]:
            self.assertEqual(self.change(**data).status_code, 400)
        self.file.refresh_from_db()
        self.assertEqual(self.file.revision, 1)

    def test_owner_isolation_and_csrf(self):
        self.client.force_login(self.other)
        self.assertEqual(self.change(name='stolen', revision=1).status_code, 404)
        self.assertEqual(self.change(trashed=True, revision=1).status_code, 404)
        self.assertEqual(self.change(trashed=False, revision=1).status_code, 404)
        self.assertEqual(self.client.get('/api/files?location=trash').json()['items'], [])
        guarded = Client(enforce_csrf_checks=True)
        guarded.force_login(self.user)
        self.assertEqual(guarded.patch(self.url, {'name': 'bad', 'revision': 1}, content_type='application/json').status_code, 403)
        self.client.logout()
        self.assertEqual(self.change(name='bad', revision=1).status_code, 401)

    def test_stale_rename_and_noop(self):
        self.assertEqual(self.change(name='before.txt', revision=1).json()['revision'], 1)
        self.assertEqual(self.change(name='after.txt', revision=1).status_code, 200)
        self.assertEqual(self.change(name='stale.txt', revision=1).status_code, 409)
        self.assertEqual(self.change(trashed=True, revision=1).status_code, 409)
        self.file.refresh_from_db()
        self.assertEqual(self.file.display_name, 'after.txt')

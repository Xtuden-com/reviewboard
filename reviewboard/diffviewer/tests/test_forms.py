import base64
import json

from django.test.client import RequestFactory
from djblets.siteconfig.models import SiteConfiguration
from reviewboard.diffviewer.errors import (DiffParserError, DiffTooBigError,
                                           EmptyDiffError)
from reviewboard.diffviewer.forms import (UploadCommitForm, UploadDiffForm,
                                          ValidateCommitForm)
from reviewboard.scmtools.errors import FileNotFoundError


class ValidateCommitFormTests(SpyAgency, TestCase):
    """Unit tests for ValidateCommitForm."""

    fixtures = ['test_scmtools']

    _PARENT_DIFF_DATA = (
        b'diff --git a/README b/README\n'
        b'new file mode 100644\n'
        b'index 0000000..94bdd3e\n'
        b'--- /dev/null\n'
        b'+++ b/README\n'
        b'@@ -0,0 +2 @@\n'
        b'+blah blah\n'
        b'+blah blah\n'
    )

    @classmethod
    def setUpClass(cls):
        super(ValidateCommitFormTests, cls).setUpClass()

        cls.request_factory = RequestFactory()

    def setUp(self):
        super(ValidateCommitFormTests, self).setUp()

        self.repository = self.create_repository(tool_name='Git')
        self.request = self.request_factory.get('/')
        self.diff = SimpleUploadedFile('diff', self.DEFAULT_GIT_FILEDIFF_DATA,
                                       content_type='text/x-patch')

    def test_clean_already_validated(self):
        """Testing ValidateCommitForm.clean for a commit that has already been
        validated
        """
        validation_info = base64.b64encode(json.dumps({
            'r1': {
                'parent_id': 'r0',
                'tree': {
                    'added': [],
                    'removed': [],
                    'modified': [],
                },
            },
        }))

        form = ValidateCommitForm(
            repository=self.repository,
            request=self.request,
            data={
                'commit_id': 'r1',
                'parent_id': 'r0',
                'validation_info': validation_info,
            },
            files={
                'diff': self.diff,
            })

        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors, {
            'validation_info': ['This commit was already validated.'],
        })

    def test_clean_parent_not_validated(self):
        """Testing ValidateCommitForm.clean for a commit whose parent has not
        been validated
        """
        validation_info = base64.b64encode(json.dumps({
            'r1': {
                'parent_id': 'r0',
                'tree': {
                    'added': [],
                    'removed': [],
                    'modified': [],
                },
            },
        }))

        form = ValidateCommitForm(
            repository=self.repository,
            request=self.request,
            data={
                'commit_id': 'r3',
                'parent_id': 'r2',
                'validation_info': validation_info,
            },
            files={
                'diff': self.diff,
            })

        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors, {
            'validation_info': ['The parent commit was not validated.'],
        })

    def test_clean_parent_diff_subsequent_commit(self):
        """Testing ValidateCommitForm.clean with a non-empty parent diff for
        a subsequent commit
        """
        validation_info = base64.b64encode(json.dumps({
            'r1': {
                'parent_id': 'r0',
                'tree': {
                    'added': [],
                    'removed': [],
                    'modified': [],
                },
            },
        }))

        parent_diff = SimpleUploadedFile('diff',
                                         self._PARENT_DIFF_DATA,
                                         content_type='text/x-patch')

        form = ValidateCommitForm(
            repository=self.repository,
            request=self.request,
            data={
                'commit_id': 'r2',
                'parent_id': 'r1',
                'validation_info': validation_info,
            },
            files={
                'diff': self.diff,
                'parent_diff': parent_diff,
            })

        self.assertTrue(form.is_valid())

    def test_clean_validation_info(self):
        """Testing ValidateCommitForm.clean_validation_info"""
        validation_info = base64.b64encode(json.dumps({
            'r1': {
                'parent_id': 'r0',
                'tree': {
                    'added': [],
                    'removed': [],
                    'modified': [],
                },
            },
        }))

        form = ValidateCommitForm(
            repository=self.repository,
            request=self.request,
            data={
                'commit_id': 'r2',
                'parent_id': 'r1',
                'validation_info': validation_info,
            },
            files={
                'diff': self.diff,
            })

        self.assertTrue(form.is_valid())

    def test_clean_validation_info_invalid_base64(self):
        """Testing ValidateCommitForm.clean_validation_info with
        non-base64-encoded data"""
        form = ValidateCommitForm(
            repository=self.repository,
            request=self.request,
            data={
                'commit_id': 'r2',
                'parent_id': 'r1',
                'validation_info': 'This is not base64!',
            },
            files={
                'diff': self.diff,
            })

        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors, {
            'validation_info': [
                'Could not parse validation info "This is not base64!": '
                'Incorrect padding',
            ],
        })

    def test_clean_validation_info_invalid_json(self):
        """Testing ValidateCommitForm.clean_validation_info with base64-encoded
        non-json data
        """
        validation_info = base64.b64encode('Not valid json.')
        form = ValidateCommitForm(
            repository=self.repository,
            request=self.request,
            data={
                'commit_id': 'r2',
                'parent_id': 'r1',
                'validation_info': validation_info,
            },
            files={
                'diff': self.diff,
            })

        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors, {
            'validation_info': [
                'Could not parse validation info "%s": No JSON object could '
                'be decoded'
                % validation_info,
            ],
        })

    def test_validate_diff(self):
        """Testing ValidateCommitForm.validate_diff"""
        self.spy_on(self.repository.get_file_exists,
                    call_fake=lambda *args, **kwargs: True)
        form = ValidateCommitForm(
            repository=self.repository,
            request=self.request,
            data={
                'commit_id': 'r1',
                'parent_id': 'r2',
            },
            files={
                'diff': self.diff,
            })

        self.assertTrue(form.is_valid())
        form.validate_diff()

    def test_validate_diff_subsequent_commit(self):
        """Testing ValidateCommitForm.validate_diff for a subsequent commit"""
        diff_content = (
            b'diff --git a/foo b/foo\n'
            b'index %s..%s 1000644\n'
            b'--- a/foo\n'
            b'+++ b/foo\n'
            b'@@ -0,0 +1,2 @@\n'
            b'+This is not a new file.\n'
            % (b'a' * 40, b'b' * 40)
        )
        diff = SimpleUploadedFile('diff', diff_content,
                                  content_type='text/x-patch')

        validation_info = base64.b64encode(json.dumps({
            'r1': {
                'parent_id': 'r0',
                'tree': {
                    'added': [{
                        'filename': 'foo',
                        'revision': 'a' * 40,
                    }],
                    'removed': [],
                    'modified': [],
                },
            },
        }))

        form = ValidateCommitForm(
            repository=self.repository,
            request=self.request,
            data={
                'commit_id': 'r2',
                'parent_id': 'r1',
                'validation_info': validation_info,
            },
            files={
                'diff': diff,
            })

        self.assertTrue(form.is_valid())
        form.validate_diff()

    def test_validate_diff_missing_files(self):
        """Testing ValidateCommitForm.validate_diff for a subsequent commit
        with missing files
        """
        validation_info = base64.b64encode(json.dumps({
            'r1': {
                'parent_id': 'r0',
                'tree': {
                    'added': [],
                    'removed': [],
                    'modified': [],
                },
            },
        }))

        form = ValidateCommitForm(
            repository=self.repository,
            request=self.request,
            data={
                'commit_id': 'r2',
                'parent_id': 'r1',
                'validation_info': validation_info,
            },
            files={
                'diff': self.diff,
            })

        self.assertTrue(form.is_valid())

        with self.assertRaises(FileNotFoundError):
            form.validate_diff()

    def test_validate_diff_empty(self):
        """Testing ValidateCommitForm.validate_diff for an empty diff"""
        form = ValidateCommitForm(
            repository=self.repository,
            request=self.request,
            data={
                'commit_id': 'r1',
                'parent_id': 'r0',
            },
            files={
                'diff': SimpleUploadedFile('diff', b' ',
                                           content_type='text/x-patch'),
            })

        self.assertTrue(form.is_valid())

        with self.assertRaises(EmptyDiffError):
            form.validate_diff()

    def test_validate_diff_too_big(self):
        """Testing ValidateCommitForm.validate_diff for a diff that is too
        large
        """
        form = ValidateCommitForm(
            repository=self.repository,
            request=self.request,
            data={
                'commit_id': 'r1',
                'parent_id': 'r0',
            },
            files={
                'diff': self.diff,
            })

        self.assertTrue(form.is_valid())

        siteconfig = SiteConfiguration.objects.get_current()
        max_diff_size = siteconfig.get('diffviewer_max_diff_size')
        siteconfig.set('diffviewer_max_diff_size', 1)
        siteconfig.save()

        with self.assertRaises(DiffTooBigError):
            try:
                form.validate_diff()
            finally:
                siteconfig.set('diffviewer_max_diff_size', max_diff_size)
                siteconfig.save()

    def test_validate_diff_parser_error(self):
        """Testing ValidateCommitForm.validate_diff for an invalid diff"""
        form = ValidateCommitForm(
            repository=self.repository,
            request=self.request,
            data={
                'commit_id': 'r1',
                'parent_id': 'r0',
            },
            files={
                'diff': SimpleUploadedFile('diff', b'asdf',
                                           content_type='text/x-patch'),
            })

        self.assertTrue(form.is_valid())

        with self.assertRaises(DiffParserError):
            form.validate_diff()
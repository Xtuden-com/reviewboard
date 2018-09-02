from django.test.client import RequestFactory
from kgb import SpyAgency
    get_original_file,
    get_original_file_from_repo,
from reviewboard.scmtools.errors import FileNotFoundError
from reviewboard.scmtools.models import Repository


class BaseFileDiffAncestorTests(SpyAgency, TestCase):
    """A base test case that creates a FileDiff history."""

    fixtures = ['test_scmtools']

    _COMMITS = [
        {
            'parent': (
                b'diff --git a/bar b/bar\n'
                b'index e69de29..5716ca5 100644\n'
                b'--- a/bar\n'
                b'+++ b/bar\n'
                b'@@ -0,0 +1 @@\n'
                b'+bar\n'
            ),
            'diff': (
                b'diff --git a/foo b/foo\n'
                b'new file mode 100644\n'
                b'index 0000000..e69de29\n'

                b'diff --git a/bar b/bar\n'
                b'index 5716ca5..8e739cc 100644\n'
                b'--- a/bar\n'
                b'+++ b/bar\n'
                b'@@ -1 +1 @@\n'
                b'-bar\n'
                b'+bar bar bar\n'
            ),
        },
        {
            'parent': (
                b'diff --git a/baz b/baz\n'
                b'new file mode 100644\n'
                b'index 0000000..7601807\n'
                b'--- /dev/null\n'
                b'+++ b/baz\n'
                b'@@ -0,0 +1 @@\n'
                b'+baz\n'
            ),
            'diff': (
                b'diff --git a/foo b/foo\n'
                b'index e69de29..257cc56 100644\n'
                b'--- a/foo\n'
                b'+++ b/foo\n'
                b'@@ -0,0 +1 @@\n'
                b'+foo\n'

                b'diff --git a/bar b/bar\n'
                b'deleted file mode 100644\n'
                b'index 8e739cc..0000000\n'
                b'--- a/bar\n'
                b'+++ /dev/null\n'
                b'@@ -1 +0,0 @@\n'
                b'-bar -bar -bar\n'

                b'diff --git a/baz b/baz\n'
                b'index 7601807..280beb2 100644\n'
                b'--- a/baz\n'
                b'+++ b/baz\n'
                b'@@ -1 +1 @@\n'
                b'-baz\n'
                b'+baz baz baz\n'
            ),
        },
        {
            'parent': (
                b'diff --git a/corge b/corge\n'
                b'new file mode 100644\n'
                b'index 0000000..e69de29\n'
            ),
            'diff': (
                b'diff --git a/foo b/qux\n'
                b'index 257cc56..03b37a0 100644\n'
                b'--- a/foo\n'
                b'+++ b/qux\n'
                b'@@ -1 +1 @@\n'
                b'-foo\n'
                b'+foo bar baz qux\n'

                b'diff --git a/bar b/bar\n'
                b'new file mode 100644\n'
                b'index 0000000..5716ca5\n'
                b'--- /dev/null\n'
                b'+++ b/bar\n'
                b'@@ -0,0 +1 @@\n'
                b'+bar\n'

                b'diff --git a/corge b/corge\n'
                b'index e69de29..f248ba3 100644\n'
                b'--- a/corge\n'
                b'+++ b/corge\n'
                b'@@ -0,0 +1 @@\n'
                b'+corge\n'
            ),
        },
    ]

    _FILES = {
        ('bar', 'e69de29'): b'',
    }

    def setUp(self):
        super(BaseFileDiffAncestorTests, self).setUp()

        def get_file(repo, path, revision, base_commit_id=None, request=None):
            if repo == self.repository:
                try:
                    return self._FILES[(path, revision)]
                except KeyError:
                    raise FileNotFoundError(path, revision,
                                            base_commit_id=base_commit_id)

            raise FileNotFoundError(path, revision,
                                    base_commit_id=base_commit_id)

        self.repository = self.create_repository(tool_name='Git')

        self.spy_on(Repository.get_file, call_fake=get_file)
        self.spy_on(Repository.get_file_exists,
                    call_fake=lambda *args, **kwargs: True)

        diffset = self.create_diffset(repository=self.repository)

        for i, diff in enumerate(self._COMMITS, 1):
            commit_id = 'r%d' % i
            parent_id = 'r%d' % (i - 1)

            self.create_diffcommit(
                diffset=diffset,
                repository=self.repository,
                commit_id=commit_id,
                parent_id=parent_id,
                diff_contents=diff['diff'],
                parent_diff_contents=diff['parent'])

        # This was only necessary so that we could side step diff validation
        # during creation.
        Repository.get_file_exists.unspy()

        self.filediffs = list(FileDiff.objects.all())


class GetOriginalFileTests(BaseFileDiffAncestorTests):
    """Unit tests for get_original_file."""

    @classmethod
    def setUpClass(cls):
        super(GetOriginalFileTests, cls).setUpClass()

        cls.request_factory = RequestFactory()

    def setUp(self):
        super(GetOriginalFileTests, self).setUp()

        self.spy_on(get_original_file_from_repo)

        self.request = self.request_factory.get('/')
        self.request._local_site_name = None

    def test_created_in_first_parent(self):
        """Test get_original_file with a file created in the parent diff of the
        first commit
        """
        filediff = FileDiff.objects.get(dest_file='bar', dest_detail='8e739cc',
                                        commit_id=1)

        self.assertEqual(get_original_file(filediff, self.request, ['ascii']),
                         b'bar\n')
        self.assertTrue(get_original_file_from_repo.called_with(
            filediff, self.request, ['ascii']))

    def test_created_in_subsequent_parent(self):
        """Test get_original_file with a file created in the parent diff of a
        subsequent commit
        """
        filediff = FileDiff.objects.get(dest_file='baz', dest_detail='280beb2',
                                        commit_id=2)

        self.assertEqual(get_original_file(filediff, self.request, ['ascii']),
                         b'baz\n')

        self.assertTrue(get_original_file_from_repo.called)

    def test_created_previously_deleted(self):
        """Testing get_original_file with a file created and previously deleted
        """
        filediff = FileDiff.objects.get(dest_file='bar', dest_detail='5716ca5',
                                        commit_id=3)

        self.assertEqual(get_original_file(filediff, self.request, ['ascii']),
                         b'')

        self.assertFalse(get_original_file_from_repo.called)

    def test_renamed(self):
        """Test get_original_file with a renamed file"""
        filediff = FileDiff.objects.get(dest_file='qux', dest_detail='03b37a0',
                                        commit_id=3)

        self.assertEqual(get_original_file(filediff, self.request, ['ascii']),
                         b'foo\n')

        self.assertFalse(get_original_file_from_repo.called)

    def test_empty_parent_diff(self):
        """Testing get_original_file with an empty parent diff"""
        filediff = (
            FileDiff.objects
            .select_related('parent_diff_hash',
                            'diffset',
                            'diffset__repository',
                            'diffset__repository__tool')
            .get(dest_file='corge',
                 dest_detail='f248ba3',
                 commit_id=3)
        )

        # FileDiff creation will set the _IS_PARENT_EMPTY flag.
        del filediff.extra_data[FileDiff._IS_PARENT_EMPTY_KEY]
        filediff.save(update_fields=('extra_data',))

        # One query for each of the following:
        # - saving the RawFileDiffData in RawFileDiffData.recompute_line_counts
        # - saving the FileDiff in FileDiff.is_parent_diff_empty
        with self.assertNumQueries(2):
            orig = get_original_file(
                filediff=filediff,
                request=self.request,
                encoding_list=['ascii'])

        self.assertEqual(orig, b'')

        # Refresh the object from the database with the parent diff attached
        # and then verify that re-calculating the original file does not cause
        # additional queries.
        filediff = (
            FileDiff.objects
            .select_related('parent_diff_hash')
            .get(pk=filediff.pk)
        )

        with self.assertNumQueries(0):
            orig = get_original_file(
                filediff=filediff,
                request=self.request_factory,
                encoding_list=['ascii'])

    def test_empty_parent_diff_precomputed(self):
        """Testing get_original_file with an empty parent diff for which the
        result has been pre-computed
        """
        filediff = (
            FileDiff.objects
            .select_related('parent_diff_hash',
                            'diffset',
                            'diffset__repository',
                            'diffset__repository__tool')
            .get(dest_file='corge',
                 dest_detail='f248ba3',
                 commit_id=3)
        )

        with self.assertNumQueries(0):
            orig = get_original_file(
                filediff=filediff,
                request=self.request,
                encoding_list=['ascii'])

        self.assertEqual(orig, b'')
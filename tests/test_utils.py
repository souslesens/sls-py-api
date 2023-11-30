from unittest import TestCase

from sls_api.utils import batched


class TestUtils(TestCase):
    def test_batched_with_empty_iterable(self):
        chunks = batched([], 10)
        self.assertCountEqual(list(chunks), [])

    def test_batched_with_valid_iterable(self):
        chunks = batched(range(0, 100), 10)

        for index, chunk in enumerate(chunks):
            self.assertEqual(len(chunk), 10)
            self.assertEqual(chunk[0], 10 * index)

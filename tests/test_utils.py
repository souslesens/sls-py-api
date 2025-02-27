from unittest import TestCase

from rdflib import Graph, BNode, URIRef, Literal, XSD

from sls_api.utils import batched, get_uri_from_str, guess_triple_type


class TestUtils(TestCase):
    def test_batched_with_empty_iterable(self):
        chunks = batched([], 10)
        self.assertCountEqual(list(chunks), [])

    def test_batched_with_valid_iterable(self):
        chunks = batched(range(0, 100), 10)

        for index, chunk in enumerate(chunks):
            self.assertEqual(len(chunk), 10)
            self.assertEqual(chunk[0], 10 * index)

    def test_get_uri_from_string_blanknode(self):
        bnode = get_uri_from_str("_:toto", Graph())
        self.assertIsInstance(bnode, BNode)
        self.assertEqual(str(bnode), "toto")
        self.assertEqual(bnode, BNode("toto"))

    def test_get_uri_from_string_blanknode_with_empty_str(self):
        bnode = get_uri_from_str("_:", Graph())
        self.assertIsInstance(bnode, BNode)
        self.assertEqual(len(bnode), 33)

    def test_get_uri_from_string_uri(self):
        uri_str = "http://example.org/toto"
        uri = get_uri_from_str(uri_str, Graph())
        self.assertIsInstance(uri, URIRef)
        self.assertEqual(uri_str, str(uri))
        self.assertEqual(uri, URIRef(uri_str))

    def test_get_uri_from_string_curie_standard(self):
        curie_str = "owl:sameAs"
        uri = get_uri_from_str(curie_str, Graph())
        self.assertEqual(uri, URIRef("http://www.w3.org/2002/07/owl#sameAs"))

    def test_get_uri_from_string_curie_custom(self):
        curie_str = "toto:titi"
        g = Graph()
        g.bind("toto", "http://example.org/toto#")
        uri = get_uri_from_str(curie_str, g)
        self.assertEqual(uri, URIRef("http://example.org/toto#titi"))

    def test_get_uri_from_string_curie_custom_error(self):
        curie_str = "toto:titi"
        with self.assertRaises(ValueError) as ctx:
            get_uri_from_str(curie_str, Graph())
        self.assertEqual(
            ctx.exception.args[0], 'Prefix "toto" not bound to any namespace.'
        )

    def test_guess_triple_type_int(self):
        res = guess_triple_type(1, Graph())
        self.assertEqual(int(res), 1)
        self.assertEqual(res, Literal(1, datatype=XSD.integer))

    def test_guess_triple_type_float(self):
        res = guess_triple_type(1.2, Graph())
        self.assertEqual(float(res), 1.2)
        self.assertEqual(res, Literal(1.2, datatype=XSD.float))

    def test_guess_triple_type_datetime(self):
        res = guess_triple_type("2025-02-27T12:16:00", Graph())
        self.assertEqual(res.datatype, XSD.dateTime)
        self.assertEqual(res, Literal("2025-02-27T12:16:00", datatype=XSD.dateTime))

    def test_guess_triple_type_date(self):
        res = guess_triple_type("2025-02-27", Graph())
        self.assertEqual(res.datatype, XSD.date)
        self.assertEqual(res, Literal("2025-02-27", datatype=XSD.date))

    def test_guess_triple_type_string(self):
        res = guess_triple_type("toto", Graph())
        self.assertEqual(str(res), "toto")
        self.assertEqual(res, Literal("toto"))

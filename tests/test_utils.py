from unittest import TestCase

from rdflib import Graph, BNode, URIRef, Literal, XSD

from sls_api.utils import (
    batched,
    get_uri_from_str,
    guess_triple_type,
    has_blank_nodes,
    replace_blank_nodes_with_uris,
)


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

    def test_has_blank_nodes_with_blank_nodes(self):
        g = Graph()
        bnode = BNode("test1")
        g.add(
            (bnode, URIRef("http://example.org/pred"), URIRef("http://example.org/obj"))
        )
        g.add(
            (
                URIRef("http://example.org/subj"),
                URIRef("http://example.org/pred"),
                bnode,
            )
        )
        self.assertTrue(has_blank_nodes(g))

    def test_has_blank_nodes_without_blank_nodes(self):
        g = Graph()
        g.add(
            (
                URIRef("http://example.org/subj"),
                URIRef("http://example.org/pred"),
                URIRef("http://example.org/obj"),
            )
        )
        g.add(
            (
                URIRef("http://example.org/subj2"),
                URIRef("http://example.org/pred2"),
                Literal("test"),
            )
        )
        self.assertFalse(has_blank_nodes(g))


class TestReplaceBlankNodesWithUris(TestCase):
    def test_bnode_in_subject_converted_to_uri(self):
        g = Graph()
        bnode = BNode("b1")
        g.add(
            (bnode, URIRef("http://example.org/pred"), URIRef("http://example.org/obj"))
        )
        result = replace_blank_nodes_with_uris(g)
        for s, p, o in result:
            self.assertIsInstance(s, URIRef)
            self.assertEqual(str(s), "_:b1")
            self.assertNotIsInstance(s, BNode)

    def test_bnode_in_object_converted_to_uri(self):
        g = Graph()
        bnode = BNode("b2")
        g.add(
            (
                URIRef("http://example.org/subj"),
                URIRef("http://example.org/pred"),
                bnode,
            )
        )
        result = replace_blank_nodes_with_uris(g)
        for s, p, o in result:
            self.assertIsInstance(o, URIRef)
            self.assertEqual(str(o), "_:b2")
            self.assertNotIsInstance(o, BNode)

    def test_connected_bnodes_preserve_references(self):
        g = Graph()
        b1 = BNode("b1")
        b2 = BNode("b2")
        g.add((b1, URIRef("http://example.org/knows"), b2))
        result = replace_blank_nodes_with_uris(g)
        for s, p, o in result:
            self.assertEqual(str(s), "_:b1")
            self.assertEqual(str(o), "_:b2")

    def test_same_bnode_references_map_to_same_uri(self):
        g = Graph()
        b1 = BNode("b1")
        g.add((b1, URIRef("http://example.org/name"), Literal("Alice")))
        g.add((b1, URIRef("http://example.org/age"), Literal("30")))
        result = replace_blank_nodes_with_uris(g)
        subjects = [s for s, p, o in result]
        self.assertEqual(len(subjects), 2)
        self.assertEqual(str(subjects[0]), "_:b1")
        self.assertEqual(str(subjects[1]), "_:b1")
        self.assertEqual(subjects[0], subjects[1])

    def test_graph_without_bnodes_unchanged(self):
        g = Graph()
        g.add(
            (
                URIRef("http://example.org/s"),
                URIRef("http://example.org/p"),
                URIRef("http://example.org/o"),
            )
        )
        result = replace_blank_nodes_with_uris(g)
        self.assertEqual(len(result), 1)
        for s, p, o in result:
            self.assertEqual(s, URIRef("http://example.org/s"))
            self.assertEqual(o, URIRef("http://example.org/o"))

    def test_empty_graph_returns_empty_graph(self):
        g = Graph()
        result = replace_blank_nodes_with_uris(g)
        self.assertEqual(len(result), 0)

from pathlib import Path
from rdflib import Graph


class RdfGraph(Graph):
    def __init__(self, graph_file_path: Path):
        super().__init__()
        self.parse(graph_file_path)

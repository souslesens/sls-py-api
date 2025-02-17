from pathlib import Path
from rdflib import Graph


class RdfGraph(Graph):
    def __init__(self, graph_file_path: Path | None = None):
        super().__init__()
        if graph_file_path:
            self.parse(graph_file_path)

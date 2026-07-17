import unittest

from openalex_client import extract_work_info, works_to_citation_graph


def work(work_id, title, references=None):
    return {
        "id": "https://openalex.org/" + work_id,
        "title": title,
        "doi": "https://doi.org/10.1000/" + work_id.lower(),
        "publication_year": 2025,
        "publication_date": "2025-01-01",
        "cited_by_count": 12,
        "authorships": [{"author": {"display_name": "A. Author"}}],
        "primary_location": {"source": {"display_name": "Journal"}},
        "primary_topic": {"display_name": "Electron microscopy"},
        "referenced_works": ["https://openalex.org/" + value for value in references or []],
        "abstract_inverted_index": {"Atomic": [0], "imaging": [1]},
    }


class OpenAlexGraphTests(unittest.TestCase):
    def test_extracts_metadata_and_rebuilds_abstract(self):
        info = extract_work_info(work("W1", "Paper one"))
        self.assertEqual(info["doi"], "10.1000/w1")
        self.assertEqual(info["abstract"], "Atomic imaging")
        self.assertEqual(info["authors"], "A. Author")

    def test_edges_only_follow_explicit_references(self):
        graph = works_to_citation_graph([
            work("W1", "Paper one", ["W2", "W999"]),
            work("W2", "Paper two"),
            work("W3", "Same topic but unrelated"),
        ])
        self.assertEqual(len(graph["nodes"]), 3)
        self.assertEqual(graph["edges"], [{
            "source": "W1", "target": "W2", "from": "W1", "to": "W2",
            "weight": 1.0, "relationship": "cites",
        }])


if __name__ == "__main__":
    unittest.main()

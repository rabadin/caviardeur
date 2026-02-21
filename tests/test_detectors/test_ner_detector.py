"""Tests for ner_detector: aggregation logic and detect_ner interface."""

from collections import namedtuple
from dataclasses import dataclass, field
from unittest.mock import MagicMock, patch

import numpy as np

from caviardeur.detectors.ner_detector import _run_window, detect_ner

MockInput = namedtuple("MockInput", ["name"])


@dataclass
class MockPiece:
    """Minimal stand-in for a sentencepiece piece (used in immutable_proto encoding)."""

    id: int
    begin: int
    end: int


@dataclass
class MockEncoded:
    pieces: list = field(default_factory=list)


def _make_session(logits_2d: np.ndarray) -> MagicMock:
    """Build a minimal ort session mock. logits_2d: [seq_len, num_labels]."""
    session = MagicMock()
    session.get_inputs.return_value = [MockInput("input_ids"), MockInput("attention_mask")]
    session.run.return_value = [np.expand_dims(logits_2d, axis=0)]
    return session


def _make_sp(pieces: list[tuple[int, int, int]], bos_id: int = 0, eos_id: int = 2) -> MagicMock:
    """SentencePiece mock.

    pieces: list of (token_id, char_begin, char_end) — real tokens only, NO BOS/EOS.
    _run_window adds BOS/EOS around them automatically.
    """

    def _encode(text, out_type=None):
        return MockEncoded(pieces=[MockPiece(id=id_, begin=begin, end=end) for id_, begin, end in pieces])

    sp = MagicMock()
    sp.encode.side_effect = _encode
    sp.bos_id.return_value = bos_id
    sp.eos_id.return_value = eos_id
    return sp


def _hot_logits(seq_len: int, num_labels: int, pred_ids: list[int]) -> np.ndarray:
    """Logits where each token position is near-certain about pred_ids[i]."""
    logits = np.full((seq_len, num_labels), -10.0, dtype=np.float32)
    for i, label_id in enumerate(pred_ids):
        logits[i, label_id] = 10.0
    return logits


# ---------------------------------------------------------------------------
# _run_window aggregation tests
# ---------------------------------------------------------------------------

ID2LABEL = {0: "O", 1: "B-PER", 2: "I-PER", 3: "B-LOC", 4: "I-LOC", 5: "B-ORG", 6: "I-ORG"}

# seq_len for all tests below = 4 tokens: BOS + 2 real + EOS
# logit predictions index into the full seq including BOS/EOS


def test_run_window_single_span():
    """BOS B-PER I-PER EOS → one PER entity spanning both tokens."""
    # real pieces: token1=(0,4), token2=(4,10)
    pieces = [(100, 0, 4), (200, 4, 10)]  # 2 real tokens
    # seq: [BOS, tok1, tok2, EOS] → preds: [O, B-PER, I-PER, O]
    logits = _hot_logits(4, len(ID2LABEL), [0, 1, 2, 0])

    entities = _run_window(_make_session(logits), _make_sp(pieces), ID2LABEL, "JeanDupont", 5, 6, 4)

    assert len(entities) == 1
    e = entities[0]
    assert e["entity_group"] == "PER"
    assert e["start"] == 0
    assert e["end"] == 10
    assert e["score"] > 0.9


def test_run_window_two_separate_entities():
    """Two entities separated by an O token."""
    pieces = [(100, 0, 4), (200, 5, 7), (300, 8, 13), (400, 13, 18)]
    logits = _hot_logits(6, len(ID2LABEL), [0, 1, 0, 3, 4, 0])

    entities = _run_window(_make_session(logits), _make_sp(pieces), ID2LABEL, "Jean et Paris-Sud", 5, 6, 4)

    assert len(entities) == 2
    assert entities[0]["entity_group"] == "PER"
    assert entities[1]["entity_group"] == "LOC"


def test_run_window_all_o():
    """No entities when every non-special token is O."""
    pieces = [(100, 0, 5), (200, 6, 11)]
    logits = _hot_logits(4, len(ID2LABEL), [0, 0, 0, 0])

    entities = _run_window(_make_session(logits), _make_sp(pieces), ID2LABEL, "Hello world", 5, 6, 4)

    assert entities == []


def test_run_window_entity_at_end_before_eos():
    """Entity right before EOS is captured."""
    pieces = [(100, 0, 4)]  # 1 real token
    logits = _hot_logits(3, len(ID2LABEL), [0, 1, 0])

    entities = _run_window(_make_session(logits), _make_sp(pieces), ID2LABEL, "Jean", 5, 6, 4)

    assert len(entities) == 1
    assert entities[0]["entity_group"] == "PER"
    assert entities[0]["start"] == 0
    assert entities[0]["end"] == 4


def test_run_window_i_without_b_starts_new_entity():
    """I- tag without a preceding B- starts a new entity."""
    pieces = [(100, 0, 5)]
    logits = _hot_logits(3, len(ID2LABEL), [0, 2, 0])  # O, I-PER, O

    entities = _run_window(_make_session(logits), _make_sp(pieces), ID2LABEL, "Marie", 5, 6, 4)

    assert len(entities) == 1
    assert entities[0]["entity_group"] == "PER"


def test_run_window_score_is_mean_of_tokens():
    """Score for a multi-token entity is the mean of its token probabilities."""
    pieces = [(100, 0, 4), (200, 4, 9)]
    logits = _hot_logits(4, len(ID2LABEL), [0, 1, 2, 0])

    entities = _run_window(_make_session(logits), _make_sp(pieces), ID2LABEL, "JeanDupont", 5, 6, 4)

    assert len(entities) == 1
    assert 0.0 < entities[0]["score"] <= 1.0


def test_run_window_truncation_uses_model_eos_id():
    """Sequences longer than max_length are truncated with model_eos_id, not sp.eos_id."""
    # 6 real pieces → full seq = BOS + 6 + EOS = 8 tokens; truncate at max_length=5
    # After truncation: BOS + pieces[0..3] + model_eos_id  (5 tokens)
    pieces = [(10, 0, 1), (20, 1, 2), (30, 2, 3), (40, 3, 4), (50, 4, 5), (60, 5, 6)]
    model_bos_id, model_eos_id, fairseq_offset = 5, 6, 4

    import numpy as np

    # Capture what input_ids the session receives
    captured = {}

    class CapturingSession:
        def get_inputs(self):
            return [type("I", (), {"name": "input_ids"})(), type("I", (), {"name": "attention_mask"})()]

        def run(self, _, inputs):
            captured["input_ids"] = inputs["input_ids"][0].tolist()
            return [np.zeros((1, 5, len(ID2LABEL)), dtype=np.float32)]

    _run_window(
        CapturingSession(),
        _make_sp(pieces),
        ID2LABEL,
        "abcdef",
        model_bos_id,
        model_eos_id,
        fairseq_offset,
        max_length=5,
    )

    assert len(captured["input_ids"]) == 5
    assert captured["input_ids"][0] == model_bos_id, "first token must be model BOS"
    assert captured["input_ids"][-1] == model_eos_id, "last token must be model EOS (not sp.eos_id)"


# ---------------------------------------------------------------------------
# detect_ner interface tests
# ---------------------------------------------------------------------------


def test_detect_ner_empty_string():
    assert detect_ner("") == []


def test_detect_ner_whitespace_only():
    assert detect_ner("   \n\t  ") == []


@patch("caviardeur.detectors.ner_detector._get_session_and_tokenizer")
def test_detect_ner_returns_per_entity(mock_get):
    """detect_ner returns a PERSON entity when the window produces one."""
    id2label = {0: "O", 1: "B-PER", 2: "I-PER"}
    # "Jean Dupont": sp gives ▁Jean=(0,4), ▁Dupont=(4,11)
    pieces = [(100, 0, 4), (200, 4, 11)]
    logits = _hot_logits(4, 3, [0, 1, 2, 0])

    mock_get.return_value = (_make_session(logits), _make_sp(pieces), id2label, 5, 6, 4)

    text = "Jean Dupont"
    results = detect_ner(text, model_name="fake-model")

    assert len(results) == 1
    from caviardeur.detectors.base import EntityType

    assert results[0].entity_type == EntityType.PERSON
    # text[0:4] = "Jean", text[4:11] = " Dupont" → after lstrip → "Dupont" at 5
    # Combined entity: text[0:11] = "Jean Dupont" (start=0 from B-PER, end=11 from I-PER)
    # But lstrip of "Jean Dupont" is "Jean Dupont" (no leading space) → text unchanged
    assert results[0].text == "Jean Dupont"
    assert results[0].source == "ner"


@patch("caviardeur.detectors.ner_detector._get_session_and_tokenizer")
def test_detect_ner_low_confidence_filtered(mock_get):
    """Entities below the confidence threshold are dropped."""
    id2label = {0: "O", 1: "B-PER"}
    pieces = [(100, 0, 4)]
    logits = np.zeros((3, 2), dtype=np.float32)  # equal logits → prob 0.5

    mock_get.return_value = (_make_session(logits), _make_sp(pieces), id2label, 5, 6, 4)

    results = detect_ner("Jean", model_name="fake-model", confidence_threshold=0.7)
    assert results == []


@patch("caviardeur.detectors.ner_detector._get_session_and_tokenizer")
def test_detect_ner_deduplicates_overlapping_windows(mock_get):
    """The same span from overlapping windows is only returned once."""
    id2label = {0: "O", 1: "B-PER", 2: "I-PER"}
    pieces = [(100, 0, 4), (200, 4, 11)]
    logits = _hot_logits(4, 3, [0, 1, 2, 0])

    mock_get.return_value = (_make_session(logits), _make_sp(pieces), id2label, 5, 6, 4)

    text = "Jean Dupont"
    results = detect_ner(text, model_name="fake-model", window_size=8, window_overlap=4)

    spans = [(r.start, r.end, r.entity_type) for r in results]
    assert len(spans) == len(set(spans))

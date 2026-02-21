import functools
import json
import logging

from .base import NER_LABEL_MAP, DetectedEntity

logger = logging.getLogger(__name__)


@functools.lru_cache(maxsize=1)
def _get_session_and_tokenizer(model_name: str):
    """Load the ONNX session and SentencePiece tokenizer on first use."""
    logger.info("Loading NER model '%s' (first run downloads ~500MB)...", model_name)
    import onnxruntime as ort
    import sentencepiece as spm
    from huggingface_hub import hf_hub_download

    model_path = hf_hub_download(repo_id=model_name, filename="model.onnx")
    config_path = hf_hub_download(repo_id=model_name, filename="config.json")
    spm_path = hf_hub_download(repo_id=model_name, filename="sentencepiece.bpe.model")

    session = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])

    sp = spm.SentencePieceProcessor()
    sp.Load(spm_path)

    with open(config_path) as f:
        config = json.load(f)
    id2label: dict[int, str] = {int(k): v for k, v in config.get("id2label", {}).items()}

    # CamemBERT (and similar fairseq-based models) shift the SentencePiece vocabulary
    # by adding special tokens before the regular vocab.  The model's BOS/EOS ids differ
    # from sp.bos_id() / sp.eos_id(); every regular token id must be offset accordingly.
    model_bos_id: int = config.get("bos_token_id", sp.bos_id())
    model_eos_id: int = config.get("eos_token_id", sp.eos_id())
    fairseq_offset: int = model_bos_id - sp.bos_id()

    logger.info("NER model loaded.")
    return session, sp, id2label, model_bos_id, model_eos_id, fairseq_offset


def _run_window(
    session,
    sp,
    id2label: dict[int, str],
    text: str,
    model_bos_id: int,
    model_eos_id: int,
    fairseq_offset: int,
    max_length: int = 512,
) -> list[dict]:
    """Run NER on one text window; returns entity dicts with entity_group/start/end/score."""
    import numpy as np

    # Tokenize with SentencePiece — proto encoding gives character-level offsets
    encoded = sp.encode(text, out_type="immutable_proto")
    pieces = list(encoded.pieces)

    # Build token sequence with BOS/EOS bookends.
    # Raw SentencePiece ids are shifted by fairseq_offset to match the model vocabulary
    # (e.g. CamemBERT adds 4 special tokens before the regular vocab: offset=4).
    ids = [model_bos_id] + [p.id + fairseq_offset for p in pieces] + [model_eos_id]
    offsets = [(0, 0)] + [(p.begin, p.end) for p in pieces] + [(0, 0)]
    special_mask = [1] + [0] * len(pieces) + [1]

    # Truncate to model max length (keep BOS and EOS)
    if len(ids) > max_length:
        ids = ids[: max_length - 1] + [model_eos_id]
        offsets = offsets[: max_length - 1] + [(0, 0)]
        special_mask = special_mask[: max_length - 1] + [1]

    input_ids = np.array([ids], dtype=np.int64)
    attention_mask = np.ones_like(input_ids)

    input_names = {inp.name for inp in session.get_inputs()}
    inputs: dict[str, np.ndarray] = {"input_ids": input_ids, "attention_mask": attention_mask}
    if "token_type_ids" in input_names:
        inputs["token_type_ids"] = np.zeros_like(input_ids)

    logits = session.run(None, inputs)[0][0]  # [seq_len, num_labels]

    # Softmax → probabilities
    logits = logits.astype(np.float32)
    exp_l = np.exp(logits - logits.max(axis=-1, keepdims=True))
    probs = exp_l / exp_l.sum(axis=-1, keepdims=True)
    pred_ids = probs.argmax(axis=-1).tolist()
    pred_scores = probs.max(axis=-1).tolist()

    # Aggregate tokens into entity spans (simple BIO strategy)
    entities: list[dict] = []
    current: dict | None = None

    for label_id, score, (char_start, char_end), is_special in zip(  # noqa: B905
        pred_ids, pred_scores, offsets, special_mask
    ):
        if is_special:
            if current is not None:
                entities.append(current)
                current = None
            continue

        label = id2label.get(label_id, "O")

        if label == "O":
            if current is not None:
                entities.append(current)
                current = None
        elif label.startswith("B-"):
            if current is not None:
                entities.append(current)
            current = {
                "entity_group": label[2:],
                "start": char_start,
                "end": char_end,
                "score": score,
                "_scores": [score],
            }
        elif label.startswith("I-"):
            entity_type = label[2:]
            if current is not None and current["entity_group"] == entity_type:
                current["end"] = char_end
                current["_scores"].append(score)
                current["score"] = float(np.mean(current["_scores"]))
            else:
                if current is not None:
                    entities.append(current)
                current = {
                    "entity_group": entity_type,
                    "start": char_start,
                    "end": char_end,
                    "score": score,
                    "_scores": [score],
                }

    if current is not None:
        entities.append(current)

    for e in entities:
        del e["_scores"]

    return entities


def detect_ner(
    text: str,
    model_name: str = "Jean-Baptiste/camembert-ner-with-dates",
    confidence_threshold: float = 0.7,
    window_size: int = 2000,
    window_overlap: int = 200,
) -> list[DetectedEntity]:
    """Detect named entities using CamemBERT NER with sliding window."""
    if not text.strip():
        return []

    session, sp, id2label, model_bos_id, model_eos_id, fairseq_offset = _get_session_and_tokenizer(model_name)
    entities: list[DetectedEntity] = []
    seen_spans: set[tuple[int, int, str]] = set()

    # Sliding window to handle CamemBERT's 512-token limit
    step = window_size - window_overlap
    starts = list(range(0, len(text), step))
    if not starts:
        starts = [0]

    for window_start in starts:
        window_end = min(window_start + window_size, len(text))
        window_text = text[window_start:window_end]

        if not window_text.strip():
            continue

        results = _run_window(session, sp, id2label, window_text, model_bos_id, model_eos_id, fairseq_offset)

        for ent in results:
            label = ent["entity_group"]
            entity_type = NER_LABEL_MAP.get(label)
            if entity_type is None:
                continue

            score = ent["score"]
            if score < confidence_threshold:
                continue

            # Map back to global offsets
            global_start = window_start + ent["start"]
            global_end = window_start + ent["end"]
            ent_text = text[global_start:global_end]

            # Trim leading/trailing whitespace from entity boundaries
            stripped = ent_text.lstrip()
            if len(stripped) < len(ent_text):
                global_start += len(ent_text) - len(stripped)
            ent_text = stripped
            stripped = ent_text.rstrip()
            if len(stripped) < len(ent_text):
                global_end -= len(ent_text) - len(stripped)
            ent_text = stripped

            if not ent_text:
                continue

            # Deduplicate entities from overlapping windows
            span_key = (global_start, global_end, label)
            if span_key in seen_spans:
                continue
            seen_spans.add(span_key)

            entities.append(
                DetectedEntity(
                    entity_type=entity_type,
                    text=ent_text,
                    start=global_start,
                    end=global_end,
                    confidence=score,
                    source="ner",
                )
            )

    return entities

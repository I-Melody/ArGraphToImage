"""
Layout recognizer — pure logic, no UI dependencies.
Analyzes page detection results and produces structured findings.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ImageInfo:
    id: str
    title: str
    image_src: str


@dataclass
class EvaluationDimension:
    label: str
    model_letter: str
    options: list
    checked_values: list = field(default_factory=list)
    remark: str = ""
    remark_found: bool = False


@dataclass
class ModelGroup:
    model_letter: str
    image: Optional[ImageInfo] = None
    dimensions: list = field(default_factory=list)


@dataclass
class RecognitionResult:
    page_type: str
    matched: bool
    reference_image: Optional[ImageInfo] = None
    model_groups: list = field(default_factory=list)
    evaluation_groups: list = field(default_factory=list)
    rank_items: list = field(default_factory=list)
    anchor_items: list = field(default_factory=list)
    model_count: int = 0
    dimension_count: int = 0


def analyze_detection(detection_data: dict) -> RecognitionResult:
    result = RecognitionResult(
        page_type=detection_data.get("page_type", "unknown"),
        matched=detection_data.get("matched", False),
        anchor_items=detection_data.get("anchor_items", []),
        rank_items=detection_data.get("rank_items", []),
    )

    ref = detection_data.get("reference_image")
    if ref:
        result.reference_image = ImageInfo(
            id=ref.get("id", ""),
            title=ref.get("title", ""),
            image_src=ref.get("image_src", ""),
        )

    model_images = detection_data.get("model_images", [])
    image_map = {}
    for mi in model_images:
        info = ImageInfo(
            id=mi.get("id", ""),
            title=mi.get("title", ""),
            image_src=mi.get("image_src", ""),
        )
        letter = _extract_model_letter(mi.get("id", ""))
        if letter:
            image_map[letter] = info

    eval_groups = detection_data.get("evaluation_groups", [])
    eval_map = {}
    for eg in eval_groups:
        letter = eg.get("model_letter", "")
        if not letter:
            continue
        if letter not in eval_map:
            eval_map[letter] = []
        for dim in eg.get("dimensions", []):
            eval_map[letter].append(EvaluationDimension(
                label=dim.get("label", ""),
                model_letter=letter,
                options=dim.get("options", []),
                checked_values=[o["value"] for o in dim.get("options", []) if o.get("checked")],
                remark=dim.get("remark", ""),
                remark_found=dim.get("remark_found", False),
            ))

    all_letters = sorted(set(list(image_map.keys()) + list(eval_map.keys())))
    for letter in all_letters:
        group = ModelGroup(
            model_letter=letter,
            image=image_map.get(letter),
            dimensions=eval_map.get(letter, []),
        )
        result.model_groups.append(group)

    result.model_count = len(result.model_groups)
    all_dims = []
    for g in result.model_groups:
        all_dims.extend(g.dimensions)
    result.dimension_count = len(set(d.label for d in all_dims))

    return result


def _extract_model_letter(grid_id: str) -> str:
    import re
    match = re.search(r'model_([A-H])', grid_id)
    return match.group(1) if match else ""

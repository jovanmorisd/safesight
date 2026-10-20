"""Association and policy rules on synthetic people (no model needed)."""
from __future__ import annotations

import numpy as np
import pytest

from ppe_core.associate import assess
from ppe_core.config import auto_class_map
from ppe_core.policy import judge
from ppe_core.types import Box, Detection, Person

ALL = {"helmet", "vest", "gloves", "boots"}
IMG_W, IMG_H = 1000, 800

# Upright person in box (100,100)-(200,400): x offsets relative to x=100
_KP = [(50, 30), (45, 25), (55, 25), (38, 28), (62, 28),  # nose, eyes, ears
       (25, 70), (75, 70), (18, 130), (82, 130), (15, 180), (85, 180),  # shoulders, elbows, wrists
       (35, 170), (65, 170), (35, 230), (65, 230), (35, 290), (65, 290)]  # hips, knees, ankles


def person(idx: int = 0, dx: float = 0.0, head_visible: bool = True) -> Person:
    kps = np.array([[100 + dx + x, 100 + y, 0.9] for x, y in _KP], dtype=float)
    if not head_visible:
        kps[0:5, 2] = 0.05
    return Person(idx, Box(100 + dx, 100, 200 + dx, 400), 0.9, kps)


def det(cls: str, x1, y1, x2, y2, conf=0.8) -> Detection:
    return Detection(cls, cls, conf, Box(x1, y1, x2, y2))


HELMET_ON_HEAD = (128, 95, 172, 130)
VEST_ON_TORSO = (120, 165, 180, 270)
HELMET_IN_LEFT_HAND = (100, 282, 132, 310)


def run(persons, dets, supported=ALL, required=("helmet", "vest")):
    out = assess(persons, dets, set(supported), IMG_W, IMG_H)
    return [judge(pa, list(required)) for pa in out]


def test_fully_equipped_worker_is_compliant():
    [pa] = run([person()], [det("helmet", *HELMET_ON_HEAD), det("vest", *VEST_ON_TORSO)])
    assert pa.items["helmet"].state == "worn"
    assert pa.items["vest"].state == "worn"
    assert pa.overall == "compliant"


def test_helmet_carried_in_hand_is_not_worn():
    [pa] = run([person()], [det("helmet", *HELMET_IN_LEFT_HAND), det("vest", *VEST_ON_TORSO)])
    assert pa.items["helmet"].state == "absent"
    assert "carried" in pa.items["helmet"].reason
    assert pa.overall == "violation" and pa.missing == ["helmet"]


def test_two_workers_one_helmet_gives_exactly_one_violation():
    a, b = person(0), person(1, dx=300)
    res = run([a, b], [det("helmet", *HELMET_ON_HEAD), det("vest", *VEST_ON_TORSO),
                       det("vest", VEST_ON_TORSO[0] + 300, VEST_ON_TORSO[1], VEST_ON_TORSO[2] + 300, VEST_ON_TORSO[3])])
    assert [pa.overall for pa in res] == ["compliant", "violation"]
    assert res[1].missing == ["helmet"]


def test_head_not_visible_is_unknown_not_violation():
    [pa] = run([person(head_visible=False)], [det("vest", *VEST_ON_TORSO)])
    assert pa.items["helmet"].state == "unknown"
    assert pa.overall == "unknown"
    assert pa.missing == [] and pa.uncertain == ["helmet"]


def test_head_box_from_detector_restores_head_region():
    p = person(head_visible=False)
    dets = [det("head", 132, 108, 168, 145), det("helmet", *HELMET_ON_HEAD), det("vest", *VEST_ON_TORSO)]
    [pa] = run([p], dets)
    assert pa.items["helmet"].state == "worn"


def test_item_the_model_cannot_detect_is_not_checked_and_never_a_violation():
    [pa] = run([person()], [det("helmet", *HELMET_ON_HEAD)], supported={"helmet"},
               required=("helmet", "vest", "gloves"))
    assert pa.items["vest"].state == "not_checked"
    assert pa.items["gloves"].state == "not_checked"
    assert pa.overall == "compliant"


def test_nothing_checkable_is_unknown():
    [pa] = run([person()], [], supported=set(), required=("helmet",))
    assert pa.overall == "unknown"


def test_tiny_person_is_unknown():
    small = Person(0, Box(10, 10, 20, 40), 0.9, None)
    [pa] = run([small], [])
    assert pa.items["helmet"].state == "unknown" and "too small" in pa.items["helmet"].reason


def test_gloves_need_every_visible_hand():
    one = [det("gloves", 105, 282, 125, 305)]
    [pa] = run([person()], one, required=("gloves",))
    assert pa.items["gloves"].state == "absent" and "1 of 2" in pa.items["gloves"].reason
    both = one + [det("gloves", 175, 282, 195, 305)]
    [pa] = run([person()], both, required=("gloves",))
    assert pa.items["gloves"].state == "worn"


def test_boots_on_ankles():
    boots = [det("boots", 125, 385, 147, 405), det("boots", 155, 385, 177, 405)]
    [pa] = run([person()], boots, required=("boots",))
    assert pa.items["boots"].state == "worn"


def test_worker_without_keypoints_falls_back_to_box_bands():
    p = Person(0, Box(100, 100, 200, 400), 0.9, None)
    [pa] = run([p], [det("helmet", *HELMET_ON_HEAD), det("vest", *VEST_ON_TORSO)])
    assert pa.overall == "compliant"
    [pa] = run([p], [det("vest", *VEST_ON_TORSO)])
    assert pa.overall == "violation"


def test_oversized_box_is_not_a_helmet():
    [pa] = run([person()], [det("helmet", 0, 0, 600, 300), det("vest", *VEST_ON_TORSO)])
    assert pa.items["helmet"].state == "absent"


@pytest.mark.parametrize("names,expected", [
    (["person", "head", "helmet", "safety-vest", "gloves", "shoes", "glasses", "face-mask-medical", "ear-mufs"],
     {"person": "person", "head": "head", "helmet": "helmet", "safety-vest": "vest", "gloves": "gloves",
      "shoes": "boots", "glasses": "goggles", "face-mask-medical": "mask", "ear-mufs": "earmuffs"}),
    (["Hardhat", "NO-Hardhat", "Safety Vest", "NO-Safety Vest", "Person", "machinery"],
     {"Hardhat": "helmet", "Safety Vest": "vest", "Person": "person"}),
    (["helmet", "no_helmet", "boots", "no_boots", "none"], {"helmet": "helmet", "boots": "boots"}),
])
def test_auto_class_map(names, expected):
    assert auto_class_map(names) == expected


def test_hungarian_matches_brute_force():
    from itertools import permutations

    from ppe_core.associate import linear_sum_assignment

    rng = np.random.default_rng(0)
    for n, m in [(1, 1), (2, 3), (3, 2), (4, 4), (5, 3), (3, 6)]:
        for _ in range(20):
            cost = rng.random((n, m))
            rows, cols = linear_sum_assignment(cost)
            got = cost[rows, cols].sum()
            k = min(n, m)
            if n <= m:
                best = min(sum(cost[i, p[i]] for i in range(n)) for p in permutations(range(m), n))
            else:
                best = min(sum(cost[p[j], j] for j in range(m)) for p in permutations(range(n), m))
            assert len(rows) == k and abs(got - best) < 1e-9

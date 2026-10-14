import copy
import json
from pathlib import Path

import pytest

from hf_fhir.extract import extract

ROOT = Path(__file__).resolve().parent.parent
LOCAL_SYSTEM = "https://chatdok.com/fhir/CodeSystem/hf-self-monitoring"


def load(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def questionnaire():
    return load("fhir/Questionnaire-hf-daily-check-in.json")


@pytest.fixture(scope="module")
def response():
    return load("examples/QuestionnaireResponse-example.json")


def walk(items):
    for item in items or []:
        yield item
        yield from walk(item.get("item"))


def loinc_check_digit_ok(code: str) -> bool:
    number, check = code.split("-")
    total = 0
    for i, ch in enumerate(reversed(number)):
        d = int(ch)
        if i % 2 == 0:
            d *= 2
            d = d // 10 + d % 10
        total += d
    return (10 - total % 10) % 10 == int(check)


def test_link_ids_are_unique(questionnaire):
    ids = [i["linkId"] for i in walk(questionnaire["item"])]
    assert len(ids) == len(set(ids))


def test_enable_when_refers_to_existing_items(questionnaire):
    ids = {i["linkId"] for i in walk(questionnaire["item"])}
    for item in walk(questionnaire["item"]):
        for cond in item.get("enableWhen", []):
            assert cond["question"] in ids


def test_loinc_codes_have_valid_check_digits(questionnaire):
    codes = [
        c["code"]
        for item in walk(questionnaire["item"])
        for c in item.get("code", [])
        if c["system"] == "http://loinc.org"
    ]
    assert codes
    assert all(loinc_check_digit_ok(c) for c in codes), codes


def test_local_codes_exist_in_code_system(questionnaire):
    defined = {c["code"] for c in load("fhir/CodeSystem-hf-self-monitoring.json")["concept"]}
    used = set()
    for item in walk(questionnaire["item"]):
        used |= {c["code"] for c in item.get("code", []) if c["system"] == LOCAL_SYSTEM}
        used |= {o["valueCoding"]["code"] for o in item.get("answerOption", [])}
    for vs in questionnaire["contained"]:
        for inc in vs["compose"]["include"]:
            used |= {c["code"] for c in inc["concept"]}
    assert used <= defined, used - defined


def test_contained_value_sets_resolve(questionnaire):
    contained = {f"#{r['id']}" for r in questionnaire["contained"]}
    for item in walk(questionnaire["item"]):
        if "answerValueSet" in item:
            assert item["answerValueSet"] in contained


def test_example_response_answers_known_items(questionnaire, response):
    ids = {i["linkId"] for i in walk(questionnaire["item"])}
    assert {i["linkId"] for i in walk(response["item"])} <= ids


def test_extraction_matches_committed_example(questionnaire, response):
    assert extract(questionnaire, response) == load("examples/Bundle-extracted-observations.json")


def test_extraction_produces_vital_signs(questionnaire, response):
    obs = [e["resource"] for e in extract(questionnaire, response)["entry"]]
    by_code = {o["code"]["coding"][0]["code"]: o for o in obs}
    assert set(by_code) == {"29463-7", "8867-4", "85354-9"}
    assert by_code["29463-7"]["valueQuantity"]["value"] == 81.6
    bp = by_code["85354-9"]
    assert [c["code"]["coding"][0]["code"] for c in bp["component"]] == ["8480-6", "8462-4"]
    assert all(o["subject"] == response["subject"] for o in obs)


def test_incomplete_blood_pressure_is_not_extracted(questionnaire, response):
    partial = copy.deepcopy(response)
    vitals = partial["item"][0]["item"]
    bp = next(i for i in vitals if i["linkId"] == "blood-pressure")
    bp["item"] = [i for i in bp["item"] if i["linkId"] != "diastolic"]
    codes = {e["resource"]["code"]["coding"][0]["code"] for e in extract(questionnaire, partial)["entry"]}
    assert "85354-9" not in codes

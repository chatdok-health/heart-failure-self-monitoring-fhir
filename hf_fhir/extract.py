"""Turn a completed daily check-in into FHIR R4 vital-sign Observations.

This is a small, dependency-free version of SDC observation-based
extraction for this one questionnaire: every item marked with the
``sdc-questionnaire-observationExtract`` extension becomes an Observation,
and the systolic and diastolic answers are combined into one blood pressure
panel (LOINC 85354-9) as the FHIR vital-signs profile expects.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

EXTRACT_URL = "http://hl7.org/fhir/uv/sdc/StructureDefinition/sdc-questionnaire-observationExtract"
UNIT_URL = "http://hl7.org/fhir/StructureDefinition/questionnaire-unit"
VITAL_SIGNS = {
    "coding": [
        {
            "system": "http://terminology.hl7.org/CodeSystem/observation-category",
            "code": "vital-signs",
            "display": "Vital Signs",
        }
    ]
}
BP_PANEL = "85354-9"
BP_PROFILE = "http://hl7.org/fhir/StructureDefinition/bp"
PROFILES = {
    "29463-7": "http://hl7.org/fhir/StructureDefinition/bodyweight",
    "8867-4": "http://hl7.org/fhir/StructureDefinition/heartrate",
}


def _walk(items, parent=None):
    for item in items or []:
        yield item, parent
        yield from _walk(item.get("item"), item)


def _answer_value(answer: dict):
    for key in ("valueDecimal", "valueInteger"):
        if key in answer:
            return answer[key]
    return None


def _quantity(value, unit_coding: dict) -> dict:
    return {
        "value": value,
        "unit": unit_coding.get("display", unit_coding["code"]),
        "system": unit_coding["system"],
        "code": unit_coding["code"],
    }


def extract(questionnaire: dict, response: dict) -> dict:
    """Return a transaction-style Bundle of Observations."""
    definitions = {item["linkId"]: (item, parent) for item, parent in _walk(questionnaire["item"])}
    answers = {
        item["linkId"]: item["answer"][0]
        for item, _ in _walk(response.get("item"))
        if item.get("answer")
    }

    base = {
        "resourceType": "Observation",
        "status": "final",
        "category": [VITAL_SIGNS],
        "subject": response["subject"],
        "effectiveDateTime": response["authored"],
        "derivedFrom": [{"reference": f"QuestionnaireResponse/{response['id']}"}],
    }

    observations = []
    bp_components = []
    for link_id, (item, parent) in definitions.items():
        ext = {e["url"]: e for e in item.get("extension", [])}
        if not ext.get(EXTRACT_URL, {}).get("valueBoolean") or link_id not in answers:
            continue
        value = _answer_value(answers[link_id])
        if value is None:
            continue
        quantity = _quantity(value, ext[UNIT_URL]["valueCoding"])
        code = {"coding": item["code"]}

        if parent and any(c["code"] == BP_PANEL for c in parent.get("code", [])):
            bp_components.append({"code": code, "valueQuantity": quantity})
            continue

        loinc = item["code"][0]["code"]
        obs = {**base, "code": code, "valueQuantity": quantity}
        if loinc in PROFILES:
            obs = {"meta": {"profile": [PROFILES[loinc]]}, **obs}
        observations.append(obs)

    # The vital-signs BP profile requires both components.
    if len(bp_components) == 2:
        panel = next(i for i, _ in definitions.values() if i["linkId"] == "blood-pressure")
        observations.append(
            {
                "meta": {"profile": [BP_PROFILE]},
                **base,
                "code": {"coding": panel["code"]},
                "component": bp_components,
            }
        )

    return {
        "resourceType": "Bundle",
        "type": "transaction",
        "entry": [
            {"resource": obs, "request": {"method": "POST", "url": "Observation"}}
            for obs in observations
        ],
    }


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        print("usage: python -m hf_fhir.extract QUESTIONNAIRE.json RESPONSE.json", file=sys.stderr)
        return 2
    q, r = (json.loads(Path(p).read_text(encoding="utf-8")) for p in argv)
    print(json.dumps(extract(q, r), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

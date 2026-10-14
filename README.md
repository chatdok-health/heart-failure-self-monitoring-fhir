# Heart Failure Self-Monitoring (HL7 FHIR R4)

**A daily check-in questionnaire for people living with heart failure, as standard FHIR resources.**

Daily weight, blood pressure, pulse and a few warning-sign questions are the core of heart-failure home monitoring. This repository publishes the daily check-in from the [ChatDok](https://chatdok.com) heart programme as interoperable HL7 FHIR R4 resources, with LOINC-coded vital signs. Any FHIR-capable app, EHR or remote-monitoring platform can render it, store the answers and turn the measurements into standard vital-sign Observations.

> ⚠️ **Not a validated clinical instrument.** This is a practical self-monitoring form, not a scored questionnaire such as the KCCQ. Warning thresholds (for example, how much weight gain should prompt a call) must be set by each patient's care team.

## Resources

| File | Resource | What it is |
|---|---|---|
| [`fhir/Questionnaire-hf-daily-check-in.json`](fhir/Questionnaire-hf-daily-check-in.json) | `Questionnaire` | The daily check-in: vital signs, seven symptom questions, medication adherence and free-text notes |
| [`fhir/CodeSystem-hf-self-monitoring.json`](fhir/CodeSystem-hf-self-monitoring.json) | `CodeSystem` | Codes for the symptom questions and answer options, with German designations |
| [`examples/QuestionnaireResponse-example.json`](examples/QuestionnaireResponse-example.json) | `QuestionnaireResponse` | A completed check-in (**synthetic**) |
| [`examples/Bundle-extracted-observations.json`](examples/Bundle-extracted-observations.json) | `Bundle` | The vital-sign Observations extracted from that response |

### What the questionnaire asks

| Section | Items | Coding |
|---|---|---|
| Measurements | Morning weight · blood pressure · resting pulse | LOINC `29463-7`, `85354-9` (`8480-6`, `8462-4`), `8867-4`, with UCUM units |
| Symptoms | Chest pain · breathing compared with usual · swelling compared with usual · needing more pillows · waking breathless · dizziness · fainting | Local codes that match [cardio-symptom-lexicon](https://github.com/chatdok-health/cardio-symptom-lexicon) concept ids |
| Medication | Took heart medication as prescribed? | Local codes |
| Notes | Free text | |

Two `display` items use `enableWhen` to show a safety message straight away: one when the patient reports chest pain, and one when they report fainting.

Measurement items carry the SDC `observationExtract` extension, so that SDC-aware tools can create Observations automatically.

## Extracting Observations

For tools without SDC support, a small dependency-free Python script does the same for this questionnaire. It produces vital-sign Observations (with the FHIR `bodyweight`, `heartrate` and `bp` profiles), and combines systolic and diastolic readings into a single blood-pressure panel:

```bash
python -m hf_fhir.extract fhir/Questionnaire-hf-daily-check-in.json examples/QuestionnaireResponse-example.json
```

The output is a transaction `Bundle` that you can POST to a FHIR server.

## Validating

The tests check internal consistency: unique link ids, valid `enableWhen` references, LOINC check digits, and local codes that exist in the CodeSystem. They also check that extraction reproduces the committed example:

```bash
python -m pytest
```

For full conformance checking, run the resources through the [HL7 FHIR validator](https://github.com/hapifhir/org.hl7.fhir.core/releases).

## Status

Version 0.1.0, status `draft`. Canonical URLs use the `https://chatdok.com/fhir/` namespace. Feedback from implementers is welcome. Please open an issue.

## License

[Apache 2.0](LICENSE). © 2026 ChatDok GmbH.

LOINC® codes are used under the LOINC license (© Regenstrief Institute, Inc.). See [loinc.org/license](https://loinc.org/license/).

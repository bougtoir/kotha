"""Generate JSON Schema (2020-12) documents for kotha-job / kotha-result 1.0 from the validator constants.

The schemas describe structure only; semantic rules (CI order, estimate inside CI, Stage C reasons,
mixed measures, hashes) are enforced by kotha.validate / kotha.contract, which remain authoritative."""
import json, os, sys
H = os.path.dirname(os.path.abspath(__file__)); PKG = os.path.dirname(H)
sys.path.insert(0, os.path.join(PKG, "src"))
from kotha import validate as v
from kotha.contract import SCHEMA_VERSION, JOB_SCHEMA, RESULT_SCHEMA

OUT = os.path.join(PKG, "src", "kotha", "schemas")
S = {"type": "string", "maxLength": v.MAX_STR}
NS = {"type": ["string", "null"], "maxLength": v.MAX_STR}
NUM = {"type": ["number", "null"]}
HASH = {"type": "string", "pattern": "^sha256:[0-9a-f]{64}$"}

estimate = {"type": "object", "additionalProperties": False, "required": ["label", "role", "effect_measure", "estimate", "verification_level"],
            "properties": {**{f: NS for f in v.ESTIMATE_FIELDS}, **{f: NUM for f in v.NUMERIC_FIELDS},
                           "label": S, "role": {"enum": list(v.ROLES)}, "effect_measure": {"enum": list(v.MEASURES)},
                           "estimand_type": {"enum": list(v.ESTIMAND_TYPES) + [None]},
                           "verification_level": {"enum": list(v.VERIFICATION_LEVELS)}}}
job = {"$schema": "https://json-schema.org/draft/2020-12/schema", "$id": f"kotha-job-{SCHEMA_VERSION}.json",
       "title": f"{JOB_SCHEMA} {SCHEMA_VERSION}", "description": __doc__, "type": "object", "additionalProperties": False,
       "required": ["schema", "schema_version", "analysis_id", "target_estimand", "clinically_relevant_ratio", "estimates"],
       "properties": {
           "schema": {"const": JOB_SCHEMA}, "schema_version": {"const": SCHEMA_VERSION},
           "analysis_id": {"type": "string", "pattern": v.ID_RE.pattern}, "title": NS,
           "target_estimand": {"type": "object", "additionalProperties": False, "required": list(v.TARGET_FIELDS),
                               "properties": {**{f: S for f in v.TARGET_FIELDS}, "effect_measure": {"enum": list(v.MEASURES)},
                                              "estimand_type": {"enum": list(v.ESTIMAND_TYPES)}}},
           "clinically_relevant_ratio": {"type": "number", "exclusiveMinimum": 0},
           "estimates": {"type": "array", "minItems": 2, "items": estimate},
           "settings": {"const": v.DEFAULT_SETTINGS},
           "stage_c": {"type": ["object", "null"], "additionalProperties": False,
                       "properties": {"judgement": {"enum": list(v.JUDGEMENTS) + [None]},
                                      "reasons": {"type": "object", "additionalProperties": False, "properties": {k: NS for k in v.REASON_KEYS}},
                                      "uncertainty": NS, "assessor": NS, "date": NS}},
           "client": {"type": "object", "description": "metadata of the creating client; excluded from input_hash"},
           "input_hash": {**HASH, "description": "sha256 of canonical JSON of the job without input_hash and client"}}}
result = {"$schema": "https://json-schema.org/draft/2020-12/schema", "$id": f"kotha-result-{SCHEMA_VERSION}.json",
          "title": f"{RESULT_SCHEMA} {SCHEMA_VERSION}", "description": "Structure of a kotha result. Integrity is checked by kotha.contract.verify_result; hash equality does not establish numerical correctness, causal validity or transportability.",
          "type": "object", "additionalProperties": False,
          "required": ["schema", "schema_version", "analysis_id", "input_hash", "job", "created_at", "validation", "provenance_complete",
                       "settings", "results", "limitations", "software", "result_hash"],
          "properties": {"schema": {"const": RESULT_SCHEMA}, "schema_version": {"const": SCHEMA_VERSION},
                         "analysis_id": {"type": "string", "pattern": v.ID_RE.pattern}, "input_hash": HASH, "job": {"$ref": f"kotha-job-{SCHEMA_VERSION}.json"},
                         "created_at": {"type": "string"}, "validation": {"type": "object", "required": ["errors", "warnings", "flags"]},
                         "provenance_complete": {"type": "boolean"}, "settings": {"type": "object"},
                         "results": {"type": "object", "required": ["primary", "rct_only", "external_summary", "conflict_diagnostics", "borrowing"],
                                     "properties": {"primary": {"const": "rct_only"}}},
                         "limitations": {"type": "array", "items": {"type": "string"}, "minItems": len(v.__dict__.get("LIMITATIONS", [])) or 1},
                         "software": {"type": "object", "required": ["kotha_version", "schema_version", "engine_sha256", "engine_matches_frozen_r1", "build", "runtime"]},
                         "result_hash": {**HASH, "description": "sha256 of canonical JSON of the result without result_hash"}}}
os.makedirs(OUT, exist_ok=True)
for name, doc in ((f"kotha-job-{SCHEMA_VERSION}.json", job), (f"kotha-result-{SCHEMA_VERSION}.json", result)):
    json.dump(doc, open(os.path.join(OUT, name), "w"), indent=1, ensure_ascii=False); open(os.path.join(OUT, name), "a").write("\n")
print(os.listdir(OUT))

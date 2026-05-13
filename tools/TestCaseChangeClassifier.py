import json
from datetime import datetime
from typing import Type
from pydantic import BaseModel, Field
from crewai.tools import BaseTool


class TestCaseChangeClassifierSchema(BaseModel):

    manifest_data: list = Field(
        ...,
        description="Previous case manifest dataset"
    )

    current_output_data: dict = Field(
        ...,
        description="Current normalized output dataset"
    )


class TestCaseChangeClassifier(BaseTool):

    name: str = "test_case_change_classifier"

    description: str = (
        "Compare normalized current cases against previous case manifest "
        "and classify them as new, changed, unchanged, "
        "or deleted_or_inactive."
    )

    args_schema: Type[BaseModel] = TestCaseChangeClassifierSchema

    def _run(
        self,
        manifest_data: list,
        current_output_data: dict
    ):

        try:

            # ---------------------------------------------------
            # LOAD INPUT DATA
            # ---------------------------------------------------

            previous_manifest = manifest_data

            current_output = current_output_data

            current_cases = current_output.get("cases", [])

            invalid_cases = current_output.get(
                "invalid_cases",
                []
            )

            # ---------------------------------------------------
            # CREATE LOOKUP MAPS
            # ---------------------------------------------------

            previous_manifest_map = {
                item["case_id"]: item
                for item in previous_manifest
            }

            current_cases_map = {
                item["case_id"]: item
                for item in current_cases
            }

            # ---------------------------------------------------
            # OUTPUT COLLECTIONS
            # ---------------------------------------------------

            new_cases = []

            changed_cases = []

            unchanged_cases = []

            deleted_or_inactive_cases = []

            # ---------------------------------------------------
            # CLASSIFY CURRENT CASES
            # ---------------------------------------------------

            for case in current_cases:

                case_id = case.get("case_id")

                record_id = case.get("record_id")

                content_hash = case.get("content_hash")

                # -----------------------------------------------
                # CASE 1 → NEW
                # -----------------------------------------------

                if case_id not in previous_manifest_map:

                    new_cases.append({
                        "case_id": case_id,
                        "record_id": record_id,
                        "content_hash": content_hash,
                        "change_status": "new",
                        "kb_action": "include_in_active_kb",
                        "requires_contextualization": True
                    })

                else:

                    previous_case = previous_manifest_map[case_id]

                    # -------------------------------------------
                    # CASE 2 → CHANGED
                    # -------------------------------------------

                    if (
                        previous_case.get("content_hash")
                        != content_hash
                    ):

                        changed_cases.append({
                            "case_id": case_id,
                            "record_id": record_id,
                            "content_hash": content_hash,
                            "change_status": "changed",
                            "kb_action": "include_in_active_kb",
                            "requires_contextualization": True
                        })

                    # -------------------------------------------
                    # CASE 3 → UNCHANGED
                    # -------------------------------------------

                    else:

                        unchanged_cases.append({
                            "case_id": case_id,
                            "record_id": record_id,
                            "content_hash": content_hash,
                            "change_status": "unchanged",
                            "kb_action": "reuse_existing_context",
                            "requires_contextualization": False
                        })

            # ---------------------------------------------------
            # CASE 4 → DELETED OR INACTIVE
            # ---------------------------------------------------

            for previous_case in previous_manifest:

                previous_case_id = previous_case.get("case_id")

                if previous_case_id not in current_cases_map:

                    deleted_or_inactive_cases.append({
                        "case_id": previous_case.get("case_id"),
                        "record_id": previous_case.get("record_id"),
                        "content_hash": previous_case.get(
                            "content_hash"
                        ),
                        "change_status": "deleted_or_inactive",
                        "kb_action": "exclude_from_active_kb",
                        "requires_contextualization": False
                    })

            # ---------------------------------------------------
            # FINAL OUTPUT
            # ---------------------------------------------------

            result = {

                "run_id": (
                    f"run_"
                    f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
                ),

                "status": "SUCCESS",

                "total_cases_fetched": len(current_cases),

                "total_valid_cases": current_output.get(
                    "total_valid_cases",
                    len(current_cases)
                ),

                "classified_count": (
                    len(new_cases)
                    + len(changed_cases)
                    + len(unchanged_cases)
                    + len(deleted_or_inactive_cases)
                ),

                "total_invalid_cases": len(invalid_cases),

                "total_new_cases": len(new_cases),

                "total_changed_cases": len(changed_cases),

                "total_unchanged_cases": len(
                    unchanged_cases
                ),

                "total_deleted_or_inactive_cases": len(
                    deleted_or_inactive_cases
                ),

                "invalid_cases": invalid_cases,

                "new_cases": new_cases,

                "changed_cases": changed_cases,

                "unchanged_cases": unchanged_cases,

                "deleted_or_inactive_cases": (
                    deleted_or_inactive_cases
                )
            }

            return json.dumps(result, indent=2)

        except Exception as e:

            error_response = {
                "status": "FAILURE",
                "error": str(e)
            }

            return json.dumps(error_response, indent=2)

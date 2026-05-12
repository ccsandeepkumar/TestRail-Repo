import requests
import json
import hashlib

from typing import Any, Type
from pydantic import BaseModel, Field
from crewai.tools import BaseTool


class TestRailExtractorInputValidatorSchema(BaseModel):
    """
    Input schema for TestRailExtractorInputValidator
    """

    testrail_url: str = Field(
        ...,
        description="Base URL of TestRail instance"
    )

    project_id: int = Field(
        ...,
        description="TestRail Project ID"
    )

    suite_id: int = Field(
        ...,
        description="TestRail Suite ID"
    )

    section_id: int = Field(
        ...,
        description="TestRail Section ID"
    )

    username: str = Field(
        ...,
        description="TestRail email/username"
    )

    api_key: str = Field(
        ...,
        description="TestRail API key"
    )

    limit: int = Field(
        250,
        description="Pagination limit"
    )


class TestRailExtractorInputValidator(BaseTool):

    name: str = "TestRail Extractor + Input Validator"

    description: str = (
        "Fetches TestRail test cases, "
        "validates required fields, "
        "normalizes schema, "
        "and generates deterministic content hash."
    )

    args_schema: Type[BaseModel] = (
        TestRailExtractorInputValidatorSchema
    )

    schema_version: str = "testrail_context.v1"

    # =====================================================
    # AUTH VALIDATION
    # =====================================================

    def _check_auth(
        self,
        base_url,
        username,
        api_key
    ):

        try:

            url = (
                f"{base_url.rstrip('/')}"
                f"/index.php?/api/v2/get_projects"
            )

            response = requests.get(
                url,
                auth=(username, api_key)
            )

            return (
                response.status_code == 200,
                response.text
            )

        except Exception as e:

            return False, str(e)

    # =====================================================
    # MAIN EXECUTION
    # =====================================================

    def _run(
        self,
        testrail_url: str,
        project_id: int,
        suite_id: int,
        section_id: int,
        username: str,
        api_key: str,
        limit: int = 250
    ) -> Any:

        base_url = testrail_url.rstrip("/")

        # =================================================
        # STEP 1: AUTH CHECK
        # =================================================

        ok, msg = self._check_auth(
            base_url,
            username,
            api_key
        )

        if not ok:

            return {
                "status": "failed",
                "error": {
                    "type": "authentication_failed",
                    "message": msg
                }
            }

        offset = 0

        valid_cases = []

        invalid_cases = []

        seen_case_ids = set()

        try:

            while True:

                # =========================================
                # TESTRAIL GET CASES API
                # =========================================

                endpoint = (
                    f"{base_url}"
                    f"/index.php?/api/v2/get_cases/"
                    f"{project_id}"
                    f"&suite_id={suite_id}"
                    f"&section_id={section_id}"
                    f"&limit={limit}"
                    f"&offset={offset}"
                )

                response = requests.get(
                    endpoint,
                    auth=(username, api_key),
                    headers={
                        "Content-Type":
                        "application/json"
                    }
                )

                if response.status_code != 200:

                    return {
                        "status": "failed",
                        "error": {
                            "type": "api_failure",
                            "status_code":
                                response.status_code,
                            "message":
                                response.text
                        }
                    }

                data = response.json()

                cases = data.get("cases", [])

                if not cases:
                    break

                # =========================================
                # PROCESS CASES
                # =========================================

                for case in cases:

                    case_id = case.get("id")

                    title = (
                        case.get("title") or ""
                    ).strip()

                    preconditions = (
                        case.get("custom_preconds")
                        or case.get("preconditions")
                        or ""
                    ).strip()

                    raw_steps = (
                        case.get("custom_steps")
                        or case.get("steps")
                        or []
                    )

                    raw_expected = (
                        case.get("custom_expected")
                        or case.get("expected_results")
                        or case.get("expected")
                        or []
                    )

                    priority = str(
                        case.get("priority_id", "")
                    )

                    type_ = str(
                        case.get("type_id", "")
                    )

                    references = (
                        case.get("refs") or []
                    )

                    # =====================================
                    # NORMALIZE STEPS
                    # =====================================

                    steps = self._normalize_text_field(
                        raw_steps
                    )

                    # =====================================
                    # NORMALIZE EXPECTED RESULTS
                    # =====================================

                    expected_results = (
                        self._normalize_text_field(
                            raw_expected
                        )
                    )

                    # =====================================
                    # NORMALIZE REFERENCES
                    # =====================================

                    references = (
                        self._normalize_references(
                            references
                        )
                    )

                    # =====================================
                    # VALIDATION
                    # =====================================

                    if (
                        not case_id
                        or not title
                        or not steps
                        or not expected_results
                    ):

                        invalid_cases.append({
                            "case_id":
                                case_id,
                            "reason":
                                "missing_required_fields"
                        })

                        continue

                    # =====================================
                    # DUPLICATE VALIDATION
                    # =====================================

                    if case_id in seen_case_ids:

                        invalid_cases.append({
                            "case_id":
                                case_id,
                            "reason":
                                "duplicate_case_id"
                        })

                        continue

                    seen_case_ids.add(case_id)

                    # =====================================
                    # CONTENT HASH PAYLOAD
                    # =====================================

                    hash_payload = {

                        "title":
                            title,

                        "preconditions":
                            preconditions,

                        "steps":
                            steps,

                        "expected_results":
                            expected_results,

                        "priority":
                            priority,

                        "type":
                            type_,

                        "references":
                            sorted(references)
                    }

                    canonical_json = json.dumps(
                        hash_payload,
                        sort_keys=True,
                        ensure_ascii=False
                    )

                    content_hash = hashlib.sha256(
                        canonical_json.encode("utf-8")
                    ).hexdigest()

                    # =====================================
                    # FINAL NORMALIZED RECORD
                    # =====================================

                    valid_cases.append({

                        "schema_version":
                            self.schema_version,

                        "case_id":
                            f"C{case_id}",

                        "record_id":
                            f"TestRail_C{case_id}",

                        "source":
                            "TestRail",

                        "project_id":
                            project_id,

                        "suite_id":
                            suite_id,

                        "section_id":
                            section_id,

                        "title":
                            title,

                        "preconditions_original":
                            preconditions,

                        "steps_original":
                            steps,

                        "expected_results_original":
                            expected_results,

                        "priority":
                            priority,

                        "type":
                            type_,

                        "references":
                            sorted(references),

                        "content_hash":
                            content_hash
                    })

                offset += limit

            # =============================================
            # FINAL RESPONSE
            # =============================================

            return {

                "status":
                    "completed",

                "total_valid_cases":
                    len(valid_cases),

                "total_invalid_cases":
                    len(invalid_cases),

                "invalid_cases":
                    invalid_cases,

                "cases":
                    valid_cases
            }

        except Exception as e:

            return {
                "status": "failed",
                "error": {
                    "type": "exception",
                    "message": str(e)
                }
            }

    # =====================================================
    # NORMALIZE TEXT FIELD
    # =====================================================

    def _normalize_text_field(
        self,
        value
    ):

        # ---------------------------------------------
        # STRING INPUT
        # ---------------------------------------------

        if isinstance(value, str):

            return [

                line.strip()

                for line in value.splitlines()

                if line.strip()
            ]

        # ---------------------------------------------
        # LIST INPUT
        # ---------------------------------------------

        elif isinstance(value, list):

            normalized = []

            for item in value:

                if isinstance(item, str):

                    cleaned = item.strip()

                    if cleaned:
                        normalized.append(cleaned)

                elif isinstance(item, dict):

                    content = (
                        item.get("content")
                        or item.get("expected")
                        or ""
                    ).strip()

                    if content:
                        normalized.append(content)

            return normalized

        return []

    # =====================================================
    # NORMALIZE REFERENCES
    # =====================================================

    def _normalize_references(
        self,
        refs
    ):

        if not refs:
            return []

        if isinstance(refs, list):

            return sorted([
                str(r).strip()
                for r in refs
                if str(r).strip()
            ])

        return sorted([

            r.strip()

            for r in str(refs).split(",")

            if r.strip()
        ])

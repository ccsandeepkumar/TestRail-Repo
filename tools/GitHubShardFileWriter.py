import json
import base64
import requests

from typing import Any, Type, List, Dict

from pydantic import BaseModel, Field

from crewai.tools import BaseTool


class GitHubShardFileWriterSchema(BaseModel):
    """
    Input schema for GitHubShardFileWriter
    """

    github_username: str = Field(
        ...,
        description="GitHub username"
    )

    github_token: str = Field(
        ...,
        description="GitHub Personal Access Token"
    )

    github_repo: str = Field(
        ...,
        description=(
            "GitHub repository name only"
        )
    )

    github_branch: str = Field(
        ...,
        description="GitHub branch name"
    )

    github_base_path: str = Field(
        ...,
        description=(
            "Base folder path inside repository"
        )
    )

    delta_shards: List[Dict[str, Any]] = Field(
        ...,
        description=(
            "List of delta shard objects"
        )
    )

    commit_message: str = Field(
        ...,
        description="GitHub commit message"
    )


class GitHubShardFileWriter(BaseTool):
    """
    Upload delta shard files to GitHub
    """

    name: str = "GitHub Shard File Writer"

    description: str = (
        "Create shard files in GitHub "
        "and upload shard test cases."
    )

    args_schema: Type[BaseModel] = (
        GitHubShardFileWriterSchema
    )

    github_api_url: str = (
        "https://api.github.com"
    )

    def _run(
        self,
        github_username: str,
        github_token: str,
        github_repo: str,
        github_branch: str,
        github_base_path: str,
        delta_shards: List[Dict[str, Any]],
        commit_message: str
    ) -> str:

        try:

            # ---------------------------------------------------
            # HEADERS
            # ---------------------------------------------------

            headers = {

                "Authorization": (
                    f"token {github_token}"
                ),

                "Accept": (
                    "application/vnd.github+json"
                )
            }

            # ---------------------------------------------------
            # OUTPUT RESULTS
            # ---------------------------------------------------

            uploaded_shards = []

            # ---------------------------------------------------
            # ITERATE SHARDS
            # ---------------------------------------------------

            for shard in delta_shards:

                # -----------------------------------------------
                # READ SHARD DATA
                # -----------------------------------------------

                shard_id = shard.get(
                    "shard_id"
                )

                shard_cases = shard.get(
                    "cases",
                    []
                )

                case_count = shard.get(
                    "case_count",
                    0
                )

                # -----------------------------------------------
                # FILE NAME
                # -----------------------------------------------

                file_name = (
                    f"{shard_id}.json"
                )

                # -----------------------------------------------
                # FULL FILE PATH
                # -----------------------------------------------

                github_file_path = (

                    f"{github_base_path.rstrip('/')}/"

                    f"{file_name}"
                )

                # -----------------------------------------------
                # FILE CONTENT
                # -----------------------------------------------

                file_content = {

                    "shard_id": shard_id,

                    "case_count": case_count,

                    "cases": shard_cases
                }

                # -----------------------------------------------
                # CONVERT TO JSON
                # -----------------------------------------------

                file_content_json = json.dumps(
                    file_content,
                    indent=4,
                    ensure_ascii=False
                )

                # -----------------------------------------------
                # BASE64 ENCODE
                # -----------------------------------------------

                encoded_content = (
                    base64.b64encode(
                        file_content_json.encode(
                            "utf-8"
                        )
                    ).decode("utf-8")
                )

                # -----------------------------------------------
                # CHECK IF FILE EXISTS
                # -----------------------------------------------

                github_get_url = (

                    f"{self.github_api_url}/repos/"

                    f"{github_username}/"

                    f"{github_repo}/contents/"

                    f"{github_file_path}"

                    f"?ref={github_branch}"
                )

                get_response = requests.get(
                    github_get_url,
                    headers=headers
                )

                existing_sha = None

                if get_response.status_code == 200:

                    existing_sha = (
                        get_response.json().get(
                            "sha"
                        )
                    )

                # -----------------------------------------------
                # PREPARE PAYLOAD
                # -----------------------------------------------

                payload = {

                    "message": (
                        f"{commit_message} - "
                        f"{shard_id}"
                    ),

                    "content": encoded_content,

                    "branch": github_branch
                }

                # -----------------------------------------------
                # ADD SHA FOR UPDATE
                # -----------------------------------------------

                if existing_sha:

                    payload["sha"] = (
                        existing_sha
                    )

                # -----------------------------------------------
                # UPLOAD FILE
                # -----------------------------------------------

                github_put_url = (

                    f"{self.github_api_url}/repos/"

                    f"{github_username}/"

                    f"{github_repo}/contents/"

                    f"{github_file_path}"
                )

                put_response = requests.put(
                    github_put_url,
                    headers=headers,
                    json=payload
                )

                # -----------------------------------------------
                # SUCCESS
                # -----------------------------------------------

                if put_response.status_code in [
                    200,
                    201
                ]:

                    uploaded_shards.append({

                        "shard_id": shard_id,

                        "github_file_path": (
                            github_file_path
                        ),

                        "case_count": case_count,

                        "upload_status": (
                            "SUCCESS"
                        )
                    })

                # -----------------------------------------------
                # FAILURE
                # -----------------------------------------------

                else:

                    uploaded_shards.append({

                        "shard_id": shard_id,

                        "github_file_path": (
                            github_file_path
                        ),

                        "case_count": case_count,

                        "upload_status": (
                            "FAILED"
                        ),

                        "github_error": (
                            put_response.text
                        )
                    })

            # ---------------------------------------------------
            # FINAL OUTPUT
            # ---------------------------------------------------

            result = {

                "status": "SUCCESS",

                "total_uploaded_shards": len(
                    uploaded_shards
                ),

                "uploaded_shards": (
                    uploaded_shards
                )
            }

            return json.dumps(
                result,
                indent=4,
                ensure_ascii=False
            )

        except Exception as e:

            error_response = {

                "status": "FAILURE",

                "error": str(e)
            }

            return json.dumps(
                error_response,
                indent=4,
                ensure_ascii=False
            )
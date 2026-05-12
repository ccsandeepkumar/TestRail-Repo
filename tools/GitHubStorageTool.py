import json
import base64
import requests

from typing import Any, Dict, Optional, Type
from pydantic import BaseModel, Field
from crewai.tools import BaseTool


class GitHubStorageToolSchema(BaseModel):
    """
    Input schema for GitHubStorageTool
    """

    operation: str = Field(
        ...,
        description="Supported operations: read or write"
    )

    repository: str = Field(
        ...,
        description="GitHub repository name"
    )

    owner: str = Field(
        ...,
        description="GitHub owner or organization"
    )

    branch: str = Field(
        default="main",
        description="GitHub branch name"
    )

    file_path: str = Field(
        ...,
        description="Target file path in repository"
    )

    github_token: str = Field(
        ...,
        description="GitHub Personal Access Token"
    )

    content: Optional[Any] = Field(
        default=None,
        description="Content to write into GitHub file"
    )

    commit_message: Optional[str] = Field(
        default="Update file from Agentic Workflow",
        description="GitHub commit message"
    )


class GitHubStorageTool(BaseTool):

    name: str = "GitHub Storage Tool"

    description: str = (
        "Reads and writes pipeline configuration, "
        "manifests, normalized outputs, "
        "and delta shards from/to GitHub."
    )

    args_schema: Type[BaseModel] = (
        GitHubStorageToolSchema
    )

    # =====================================================
    # MAIN EXECUTION
    # =====================================================

    def _run(
        self,
        operation: str,
        repository: str,
        owner: str,
        branch: str,
        file_path: str,
        github_token: str,
        content: Optional[Any] = None,
        commit_message: str = (
            "Update file from Agentic Workflow"
        )
    ) -> Dict[str, Any]:

        try:

            operation = operation.lower().strip()

            # =============================================
            # READ OPERATION
            # =============================================

            if operation == "read":

                return self._read_file(
                    owner=owner,
                    repository=repository,
                    branch=branch,
                    file_path=file_path,
                    github_token=github_token
                )

            # =============================================
            # WRITE OPERATION
            # =============================================

            elif operation == "write":

                return self._write_file(
                    owner=owner,
                    repository=repository,
                    branch=branch,
                    file_path=file_path,
                    github_token=github_token,
                    content=content,
                    commit_message=commit_message
                )

            # =============================================
            # INVALID OPERATION
            # =============================================

            else:

                return {

                    "status":
                        "failed",

                    "error": {

                        "type":
                            "invalid_operation",

                        "message":
                            (
                                "Supported operations: "
                                "read, write"
                            )
                    }
                }

        except Exception as e:

            return {

                "status":
                    "failed",

                "error": {

                    "type":
                        "tool_execution_failure",

                    "message":
                        str(e)
                }
            }

    # =====================================================
    # READ FILE
    # =====================================================

    def _read_file(
        self,
        owner: str,
        repository: str,
        branch: str,
        file_path: str,
        github_token: str
    ) -> Dict[str, Any]:

        try:

            url = (
                f"https://api.github.com/repos/"
                f"{owner}/{repository}/contents/"
                f"{file_path}?ref={branch}"
            )

            headers = {

                "Authorization":
                    f"Bearer {github_token}",

                "Accept":
                    "application/vnd.github+json"
            }

            response = requests.get(
                url,
                headers=headers
            )

            # =============================================
            # DEBUG LOGS
            # =============================================

            print("\n========== GITHUB READ ==========")
            print(f"URL: {url}")
            print(f"Status Code: {response.status_code}")

            # =============================================
            # FILE NOT FOUND
            # =============================================

            if response.status_code == 404:

                return {

                    "status":
                        "success",

                    "operation":
                        "read",

                    "file_exists":
                        False,

                    "message":
                        (
                            "File does not exist yet "
                            "(expected during first run)"
                        ),

                    "content":
                        []
                }

            # =============================================
            # API FAILURE
            # =============================================

            if response.status_code != 200:

                return {

                    "status":
                        "failed",

                    "error": {

                        "type":
                            "github_read_failure",

                        "status_code":
                            response.status_code,

                        "message":
                            response.text
                    }
                }

            payload = response.json()

            encoded_content = payload.get(
                "content",
                ""
            )

            if not encoded_content:

                return {

                    "status":
                        "failed",

                    "error": {

                        "type":
                            "empty_github_content",

                        "message":
                            "GitHub content is empty"
                    }
                }

            # =============================================
            # BASE64 DECODE
            # =============================================

            decoded_content = base64.b64decode(
                encoded_content
            ).decode("utf-8")

            print("\n========== RAW CONTENT ==========")
            print(decoded_content)

            # =============================================
            # TRY JSON PARSE
            # =============================================

            parsed_content = decoded_content

            try:

                parsed_content = json.loads(
                    decoded_content
                )

            except Exception:

                pass

            return {

                "status":
                    "success",

                "operation":
                    "read",

                "file_exists":
                    True,

                "repository":
                    repository,

                "branch":
                    branch,

                "file_path":
                    file_path,

                "sha":
                    payload.get("sha"),

                "raw_content":
                    decoded_content,

                "content":
                    parsed_content
            }

        except Exception as e:

            return {

                "status":
                    "failed",

                "error": {

                    "type":
                        "github_read_exception",

                    "message":
                        str(e)
                }
            }

    # =====================================================
    # WRITE FILE
    # =====================================================

    def _write_file(
        self,
        owner: str,
        repository: str,
        branch: str,
        file_path: str,
        github_token: str,
        content: Any,
        commit_message: str
    ) -> Dict[str, Any]:

        try:

            # =============================================
            # FETCH EXISTING FILE
            # =============================================

            existing_file = self._read_file(
                owner=owner,
                repository=repository,
                branch=branch,
                file_path=file_path,
                github_token=github_token
            )

            existing_sha = existing_file.get("sha")

            # =============================================
            # SERIALIZE CONTENT
            # =============================================

            if isinstance(content, str):

                serialized_content = content

            else:

                serialized_content = json.dumps(
                    content,
                    indent=2,
                    ensure_ascii=False
                )

            encoded_content = base64.b64encode(
                serialized_content.encode("utf-8")
            ).decode("utf-8")

            url = (
                f"https://api.github.com/repos/"
                f"{owner}/{repository}/contents/"
                f"{file_path}"
            )

            headers = {

                "Authorization":
                    f"Bearer {github_token}",

                "Accept":
                    "application/vnd.github+json"
            }

            payload = {

                "message":
                    commit_message,

                "content":
                    encoded_content,

                "branch":
                    branch
            }

            # =============================================
            # UPDATE EXISTING FILE
            # =============================================

            if existing_sha:

                payload["sha"] = existing_sha

            print("\n========== GITHUB WRITE ==========")
            print(f"URL: {url}")
            print(f"Commit Message: {commit_message}")

            response = requests.put(
                url,
                headers=headers,
                json=payload
            )

            print(f"Status Code: {response.status_code}")

            # =============================================
            # FAILURE
            # =============================================

            if response.status_code not in [200, 201]:

                return {

                    "status":
                        "failed",

                    "error": {

                        "type":
                            "github_write_failure",

                        "status_code":
                            response.status_code,

                        "message":
                            response.text
                    }
                }

            result = response.json()

            return {

                "status":
                    "success",

                "operation":
                    "write",

                "repository":
                    repository,

                "branch":
                    branch,

                "file_path":
                    file_path,

                "commit_sha":
                    result.get(
                        "commit",
                        {}
                    ).get("sha"),

                "content_sha":
                    result.get(
                        "content",
                        {}
                    ).get("sha"),

                "message":
                    "GitHub file updated successfully"
            }

        except Exception as e:

            return {

                "status":
                    "failed",

                "error": {

                    "type":
                        "github_write_exception",

                    "message":
                        str(e)
                }
            }

"""
The Tribunal Integration Service for Catalyze.

Provides direct integration with The Tribunal (CVA - Contextual Verification Agent)
for Synapse tier users. Sends Success Specs for intent preservation verification.

Feature Flag: Only available for Synapse (Pro) tier users.
"""

import os
import json
import uuid
import httpx
from typing import Dict, Any, Optional, Sequence
from dataclasses import dataclass

try:
    # Preferred: unified contract package (Phase 2)
    from catalyze_contract import SuccessSpec  # type: ignore
except Exception:
    # Fallback: local Promptly schema (Phase 1 compatibility)
    from .schemas import SuccessSpec


# ============================================================================
# CONFIGURATION
# ============================================================================

TRIBUNAL_API_URL = os.getenv("TRIBUNAL_API_URL", "http://localhost:8001")

# Shared key for CVA Tribunal endpoints.
# CVA expects this as CVA_API_TOKEN server-side.
TRIBUNAL_API_TOKEN = (
    os.getenv("TRIBUNAL_API_TOKEN", "")
    or os.getenv("TRIBUNAL_API_KEY", "")
    or os.getenv("CVA_API_TOKEN", "")
)

TRIBUNAL_TIMEOUT = int(os.getenv("TRIBUNAL_TIMEOUT", "30"))


@dataclass
class TribunalResponse:
    """Response from The Tribunal verification."""
    success: bool
    run_id: Optional[str] = None
    project_id: Optional[str] = None
    status: str = "pending"
    message: str = ""
    verdicts_url: Optional[str] = None


class TribunalService:
    """
    Service for The Tribunal integration.
    
    Handles sending Success Specs to The Tribunal for downstream
    verification of optimized prompts.
    """
    
    def __init__(self):
        self._api_url = TRIBUNAL_API_URL.rstrip("/")
        self._api_token = TRIBUNAL_API_TOKEN
        self._timeout = TRIBUNAL_TIMEOUT
    
    @property
    def is_configured(self) -> bool:
        """Check if The Tribunal API is configured."""
        return bool(self._api_url)
    
    @property
    def has_api_key(self) -> bool:
        """Check if API key is set for authenticated requests."""
        return bool(self._api_token)

    def _auth_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._api_token:
            headers["Authorization"] = f"Bearer {self._api_token}"
        return headers

    async def _upload_artifacts_async(
        self,
        *,
        project_id: str,
        optimized_prompt: str,
        original_idea: str,
        success_spec: SuccessSpec,
        extra_files: Optional[Sequence[tuple[str, bytes, str]]] = None,
    ) -> None:
        """Upload a minimal project payload to CVA so Tribunal scans have a project_root.

        CVA /upload requires at least one file and (if upload_id provided) it must be alphanumeric.
        """

        optimized_prompt = (optimized_prompt or "")[:100_000]
        original_idea = (original_idea or "")[:100_000]
        success_spec_json = json.dumps(success_spec.model_dump(), ensure_ascii=False, indent=2)[:200_000]

        files: list[tuple[str, tuple[str, bytes, str]]] = [
            ("files", ("optimized_prompt.txt", optimized_prompt.encode("utf-8"), "text/plain")),
            ("files", ("original_idea.txt", original_idea.encode("utf-8"), "text/plain")),
            ("files", ("success_spec.json", success_spec_json.encode("utf-8"), "application/json")),
        ]

        data: list[tuple[str, str]] = [
            ("upload_id", project_id),
            ("paths", "optimized_prompt.txt"),
            ("paths", "original_idea.txt"),
            ("paths", "success_spec.json"),
        ]

        if extra_files:
            for rel_path, content, mime in extra_files:
                safe_rel = (rel_path or "").replace("\\\\", "/").lstrip("/")
                if not safe_rel:
                    continue
                safe_name = safe_rel.split("/")[-1]
                files.append(("files", (safe_name, content, mime)))
                data.append(("paths", safe_rel))

        headers: Dict[str, str] = {}
        if self._api_token:
            headers["Authorization"] = f"Bearer {self._api_token}"

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                f"{self._api_url}/upload",
                data=data,
                files=files,
                headers=headers,
            )

        if resp.status_code >= 400:
            raise RuntimeError(f"CVA upload failed: {resp.status_code}")
    
    async def submit_for_verification_async(
        self,
        success_spec: SuccessSpec,
        optimized_prompt: str,
        original_idea: str,
        user_tier: str = "synapse",
        *,
        callback_url: Optional[str] = None,
        callback_bearer_token: Optional[str] = None,
        scan_mode: str = "full",
    ) -> TribunalResponse:
        """
        Submit intent to CVA Tribunal and enqueue a scan (async).
        
        Integration contract:
        - Create run_id (UUID)
        - Upload minimal artifacts into CVA upload store (project_id)
        - POST /api/intent (requires Bearer token)
        - POST /api/trigger_scan (requires Bearer token)
        
        Args:
            success_spec: The Success Spec from optimization
            optimized_prompt: The final optimized prompt
            original_idea: User's original idea
            user_tier: User's subscription tier
            callback_url: Optional webhook callback URL for CVA completion events
            callback_bearer_token: Optional bearer token forwarded to callback
            scan_mode: "diff" or "full" (default: full for prompt artifacts)
            
        Returns:
            TribunalResponse with verification status
        """
        if user_tier not in ("synapse", "pro", "enterprise", "admin"):
            return TribunalResponse(
                success=False,
                status="unauthorized",
                message="The Tribunal integration requires Synapse tier or higher"
            )

        if not self._api_token:
            return TribunalResponse(
                success=False,
                status="misconfigured",
                message="Missing TRIBUNAL_API_TOKEN (must match CVA_API_TOKEN on the Tribunal server)",
            )

        run_uuid = uuid.uuid4()
        run_id = str(run_uuid)
        project_id = run_uuid.hex  # must be alphanumeric to satisfy CVA /upload

        try:
            await self._upload_artifacts_async(
                project_id=project_id,
                optimized_prompt=optimized_prompt,
                original_idea=original_idea,
                success_spec=success_spec,
            )

            intent_payload: Dict[str, Any] = {
                "run_id": run_id,
                "project_id": project_id,
                "success_spec": success_spec.model_dump(),
            }
            if callback_url:
                intent_payload["initiator"] = {
                    "callback_url": callback_url,
                    "callback_bearer_token": callback_bearer_token,
                }

            async with httpx.AsyncClient(timeout=self._timeout) as client:
                intent_resp = await client.post(
                    f"{self._api_url}/api/intent",
                    json=intent_payload,
                    headers=self._auth_headers(),
                )
                if intent_resp.status_code >= 400:
                    return TribunalResponse(
                        success=False,
                        run_id=run_id,
                        project_id=project_id,
                        status="error",
                        message=f"The Tribunal /api/intent returned {intent_resp.status_code}",
                    )

                trigger_resp = await client.post(
                    f"{self._api_url}/api/trigger_scan",
                    json={"run_id": run_id, "mode": scan_mode},
                    headers=self._auth_headers(),
                )
                if trigger_resp.status_code >= 400:
                    return TribunalResponse(
                        success=False,
                        run_id=run_id,
                        project_id=project_id,
                        status="error",
                        message=f"The Tribunal /api/trigger_scan returned {trigger_resp.status_code}",
                    )

                data = trigger_resp.json()
                return TribunalResponse(
                    success=True,
                    run_id=run_id,
                    project_id=project_id,
                    status=str(data.get("status") or "queued"),
                    message="Submitted to The Tribunal",
                    verdicts_url=data.get("verdicts_url"),
                )
        
        except httpx.TimeoutException:
            return TribunalResponse(
                success=False,
                run_id=run_id,
                project_id=project_id,
                status="timeout",
                message="The Tribunal request timed out"
            )
        except httpx.ConnectError:
            return TribunalResponse(
                success=False,
                run_id=run_id,
                project_id=project_id,
                status="offline",
                message="The Tribunal service is not available"
            )
        except Exception as e:
            return TribunalResponse(
                success=False,
                run_id=run_id,
                project_id=project_id,
                status="error",
                message=f"Failed to connect to The Tribunal: {str(e)}"
            )
    
    def submit_for_verification(
        self,
        success_spec: SuccessSpec,
        optimized_prompt: str,
        original_idea: str,
        user_tier: str = "synapse"
    ) -> TribunalResponse:
        """Sync wrapper around the async Tribunal submission."""
        import asyncio

        return asyncio.run(
            self.submit_for_verification_async(
                success_spec=success_spec,
                optimized_prompt=optimized_prompt,
                original_idea=original_idea,
                user_tier=user_tier,
            )
        )


# Singleton instance
_tribunal_service: Optional[TribunalService] = None


def get_tribunal_service() -> TribunalService:
    """Get or create the Tribunal service singleton."""
    global _tribunal_service
    if _tribunal_service is None:
        _tribunal_service = TribunalService()
    return _tribunal_service

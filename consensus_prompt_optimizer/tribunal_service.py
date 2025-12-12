"""
The Tribunal Integration Service for Catalyze.

Provides direct integration with The Tribunal (CVA - Contextual Verification Agent)
for Synapse tier users. Sends Success Specs for intent preservation verification.

Feature Flag: Only available for Synapse (Pro) tier users.
"""

import os
import json
import httpx
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass

from .schemas import SuccessSpec


# ============================================================================
# CONFIGURATION
# ============================================================================

TRIBUNAL_API_URL = os.getenv("TRIBUNAL_API_URL", "http://localhost:8001")
TRIBUNAL_API_KEY = os.getenv("TRIBUNAL_API_KEY", "")
TRIBUNAL_TIMEOUT = int(os.getenv("TRIBUNAL_TIMEOUT", "30"))


@dataclass
class TribunalResponse:
    """Response from The Tribunal verification."""
    success: bool
    verification_id: Optional[str] = None
    status: str = "pending"
    message: str = ""
    tribunal_url: Optional[str] = None


class TribunalService:
    """
    Service for The Tribunal integration.
    
    Handles sending Success Specs to The Tribunal for downstream
    verification of optimized prompts.
    """
    
    def __init__(self):
        self._api_url = TRIBUNAL_API_URL.rstrip("/")
        self._api_key = TRIBUNAL_API_KEY
        self._timeout = TRIBUNAL_TIMEOUT
    
    @property
    def is_configured(self) -> bool:
        """Check if The Tribunal API is configured."""
        return bool(self._api_url)
    
    @property
    def has_api_key(self) -> bool:
        """Check if API key is set for authenticated requests."""
        return bool(self._api_key)
    
    def build_tribunal_context(
        self,
        success_spec: SuccessSpec,
        optimized_prompt: str,
        original_idea: str,
        user_tier: str = "synapse"
    ) -> Dict[str, Any]:
        """
        Build the tribunal_context payload for The Tribunal.
        
        Args:
            success_spec: The Success Spec from Catalyze
            optimized_prompt: The final optimized prompt
            original_idea: The user's original idea
            user_tier: The user's subscription tier
            
        Returns:
            tribunal_context payload ready for API submission
        """
        return {
            "source": "catalyze",
            "version": "v2",
            "tier": user_tier,
            "tribunal_context": {
                "intent_summary": success_spec.intent_summary,
                "key_constraints": success_spec.key_constraints,
                "expected_behavior": success_spec.expected_behavior,
            },
            "artifacts": {
                "optimized_prompt": optimized_prompt,
                "original_idea": original_idea[:500],
            },
            "verification_requested": True,
        }
    
    async def submit_for_verification_async(
        self,
        success_spec: SuccessSpec,
        optimized_prompt: str,
        original_idea: str,
        user_tier: str = "synapse"
    ) -> TribunalResponse:
        """
        Submit Success Spec to The Tribunal for verification (async).
        
        Only available for Synapse tier users (cva_direct_link = True).
        
        Args:
            success_spec: The Success Spec from optimization
            optimized_prompt: The final optimized prompt
            original_idea: User's original idea
            user_tier: User's subscription tier
            
        Returns:
            TribunalResponse with verification status
        """
        if user_tier not in ("synapse", "pro", "enterprise"):
            return TribunalResponse(
                success=False,
                status="unauthorized",
                message="The Tribunal integration requires Synapse tier or higher"
            )
        
        payload = self.build_tribunal_context(
            success_spec, optimized_prompt, original_idea, user_tier
        )
        
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{self._api_url}/api/verify",
                    json=payload,
                    headers=headers
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return TribunalResponse(
                        success=True,
                        verification_id=data.get("verification_id"),
                        status=data.get("status", "submitted"),
                        message="Successfully submitted to The Tribunal",
                        tribunal_url=data.get("tribunal_url")
                    )
                else:
                    return TribunalResponse(
                        success=False,
                        status="error",
                        message=f"The Tribunal returned status {response.status_code}"
                    )
                    
        except httpx.TimeoutException:
            return TribunalResponse(
                success=False,
                status="timeout",
                message="The Tribunal request timed out"
            )
        except httpx.ConnectError:
            return TribunalResponse(
                success=False,
                status="offline",
                message="The Tribunal service is not available"
            )
        except Exception as e:
            return TribunalResponse(
                success=False,
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
        """
        Submit Success Spec to The Tribunal for verification (sync).
        
        Synchronous wrapper for submit_for_verification_async.
        Simulates the call if The Tribunal is not running locally.
        """
        if user_tier not in ("synapse", "pro", "enterprise"):
            return TribunalResponse(
                success=False,
                status="unauthorized",
                message="The Tribunal integration requires Synapse tier or higher"
            )
        
        payload = self.build_tribunal_context(
            success_spec, optimized_prompt, original_idea, user_tier
        )
        
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        
        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.post(
                    f"{self._api_url}/api/verify",
                    json=payload,
                    headers=headers
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return TribunalResponse(
                        success=True,
                        verification_id=data.get("verification_id"),
                        status=data.get("status", "submitted"),
                        message="Successfully submitted to The Tribunal",
                        tribunal_url=data.get("tribunal_url")
                    )
                else:
                    return TribunalResponse(
                        success=False,
                        status="error",
                        message=f"The Tribunal returned status {response.status_code}"
                    )
                    
        except httpx.ConnectError:
            # The Tribunal not running - simulate success for development
            return self._simulate_tribunal_response(payload)
        except Exception as e:
            return TribunalResponse(
                success=False,
                status="error",
                message=f"Failed to connect to The Tribunal: {str(e)}"
            )
    
    def _simulate_tribunal_response(self, payload: Dict[str, Any]) -> TribunalResponse:
        """
        Simulate The Tribunal response when service is not available.
        
        Used for development/testing when The Tribunal is not running locally.
        """
        import hashlib
        
        # Generate a simulated verification ID
        payload_hash = hashlib.sha256(
            json.dumps(payload, sort_keys=True).encode()
        ).hexdigest()[:12]
        
        return TribunalResponse(
            success=True,
            verification_id=f"sim_{payload_hash}",
            status="simulated",
            message="The Tribunal link prepared (service offline - simulated response)",
            tribunal_url=f"tribunal://verify/{payload_hash}"
        )


# Singleton instance
_tribunal_service: Optional[TribunalService] = None


def get_tribunal_service() -> TribunalService:
    """Get or create the Tribunal service singleton."""
    global _tribunal_service
    if _tribunal_service is None:
        _tribunal_service = TribunalService()
    return _tribunal_service

"""
API Client - Communication with TryFitted API

This module handles all HTTP communication with the TryFitted API,
including job status updates and callbacks.
"""

import requests
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class APIClient:
    """TryFitted API client"""
    
    def __init__(self, base_url: str):
        """
        Initialize API client
        
        Args:
            base_url: Base URL of TryFitted API
        """
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        logger.info(f"Initialized API client: {base_url}")
    
    def update_job_status(
        self,
        job_id: str,
        status: str,
        error: Optional[str] = None,
        progress: Optional[int] = None,
        result: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Update avatar job status
        
        Args:
            job_id: Job ID
            status: Job status ("processing", "completed", "failed")
            error: Error message (if failed)
            progress: Progress percentage (0-100)
            result: Result data (glbUrl, measurements, etc.) if completed
            
        Returns:
            True if successful, False otherwise
        """
        try:
            url = f"{self.base_url}/v1/avatar/jobs/{job_id}/status"
            payload = {
                "status": status,
                "error": error,
                "progress": progress,
            }
            if result:
                payload["result"] = result
            
            logger.info(f"Updating job {job_id} status to: {status}")
            response = self.session.patch(url, json=payload, timeout=10)
            response.raise_for_status()
            
            return True
            
        except requests.RequestException as e:
            logger.error(f"Failed to update job status: {e}")
            return False
    
    def create_avatar(
        self,
        job_id: str,
        user_id: str,
        glb_url: str,
        measurements: Dict[str, float],
        quality_report: Dict[str, Any]
    ) -> Optional[str]:
        """
        Create avatar record
        
        Args:
            job_id: Job ID
            user_id: User ID
            glb_url: GLB file URL
            measurements: Body measurements
            quality_report: Quality report
            
        Returns:
            Avatar ID if successful, None otherwise
        """
        try:
            url = f"{self.base_url}/v1/avatars"
            payload = {
                "jobId": job_id,
                "userId": user_id,
                "glbUrl": glb_url,
                "measurements": measurements,
                "qualityReport": quality_report,
            }
            
            logger.info(f"Creating avatar for job {job_id}")
            response = self.session.post(url, json=payload, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            return data.get("id")
            
        except requests.RequestException as e:
            logger.error(f"Failed to create avatar: {e}")
            return None

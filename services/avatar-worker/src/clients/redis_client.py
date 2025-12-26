"""
Redis Client - Connection to Redis/BullMQ

This module handles Redis connection for job queue consumption.
"""

import redis
import json
import logging
from typing import Dict, Any, Optional, Callable
import time

logger = logging.getLogger(__name__)


class RedisClient:
    """Redis client for BullMQ job consumption"""
    
    def __init__(self, redis_url: str):
        """
        Initialize Redis client
        
        Args:
            redis_url: Redis connection URL (e.g., redis://localhost:6379)
        """
        self.redis_url = redis_url
        self.client = None
        
        logger.info(f"Initializing Redis client: {redis_url}")
        self._connect()
    
    def _connect(self):
        """Connect to Redis"""
        try:
            self.client = redis.from_url(self.redis_url, decode_responses=True)
            self.client.ping()
            logger.info("Successfully connected to Redis")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
    
    def consume_jobs(self, queue_name: str, job_handler: Callable[[Dict[str, Any]], bool], poll_interval: int = 1):
        """
        Consume jobs from BullMQ queue
        
        Args:
            queue_name: Name of the queue to consume from
            job_handler: Function to handle each job (returns True if successful)
            poll_interval: Seconds to wait between polls
        """
        logger.info(f"Starting job consumption from queue: {queue_name}")
        
        # BullMQ queue keys
        wait_key = f"bull:{queue_name}:wait"
        active_key = f"bull:{queue_name}:active"
        completed_key = f"bull:{queue_name}:completed"
        failed_key = f"bull:{queue_name}:failed"
        
        while True:
            try:
                # Move job from wait to active (BRPOPLPUSH with timeout)
                job_id = self.client.brpoplpush(wait_key, active_key, timeout=poll_interval)
                
                if not job_id:
                    continue
                
                logger.info(f"Processing job: {job_id}")
                
                # Get job data (BullMQ stored jobs as Hash)
                job_key = f"bull:{queue_name}:{job_id}"
                job_hash = self.client.hgetall(job_key)
                
                if not job_hash:
                    logger.error(f"Job data not found for {job_id}")
                    self.client.lrem(active_key, 1, job_id)
                    continue

                logger.info(f"Raw job data keys: {job_hash.keys()}")
                if 'data' in job_hash:
                    logger.info(f"Job Data content: {job_hash['data']}")
                
                # Parse job data
                try:
                    # BullMQ stores data in 'data' field, but sometimes it might be in root if not wrapped?
                    # Check if 'data' exists, otherwise try to use the whole hash or look for specific fields
                    if 'data' in job_hash:
                        job_data_str = job_hash['data']
                        job_data = json.loads(job_data_str) if job_data_str else {}
                    else:
                         # Fallback: maybe it's not wrapped? Or updated BullMQ version?
                         # For now, let's assume empty and log warning
                         logger.warning(f"No 'data' field in job hash for {job_id}")
                         job_data = {}
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse job data JSON: {e}")
                    self.client.lrem(active_key, 1, job_id)
                    continue
                
                # Process job
                try:
                    success = job_handler(job_data)
                    
                    if success:
                        # Move to completed
                        self.client.lrem(active_key, 1, job_id)
                        self.client.lpush(completed_key, job_id)
                        logger.info(f"Job {job_id} completed successfully")
                    else:
                        # Move to failed
                        self.client.lrem(active_key, 1, job_id)
                        self.client.lpush(failed_key, job_id)
                        logger.error(f"Job {job_id} failed")
                        
                except Exception as e:
                    logger.error(f"Error processing job {job_id}: {e}", exc_info=True)
                    # Move to failed
                    self.client.lrem(active_key, 1, job_id)
                    self.client.lpush(failed_key, job_id)
                    
            except KeyboardInterrupt:
                logger.info("Job consumption interrupted")
                break
            except Exception as e:
                logger.error(f"Error in job consumption loop: {e}", exc_info=True)
                time.sleep(poll_interval)

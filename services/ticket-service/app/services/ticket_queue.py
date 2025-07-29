import json
import uuid
from datetime import datetime
from typing import Dict, Optional
import structlog

logger = structlog.get_logger()

class TicketQueue:
    def __init__(self, redis_client):
        self.redis = redis_client
        self.queue_key = "pending_tickets"
        self.status_key = "ticket_status"
    
    async def add_ticket(self, ticket_request) -> str:
        """Add a ticket to the processing queue"""
        try:
            queue_id = f"queue_{uuid.uuid4().hex[:8]}"
            
            queue_item = {
                'id': queue_id,
                'ticket_data': ticket_request.dict(),
                'attempts': 0,
                'max_attempts': 10,
                'created_at': datetime.now().isoformat(),
                'status': 'queued',
                'error': None
            }
            
            # Add to queue
            await self.redis.redis.lpush(self.queue_key, json.dumps(queue_item))
            
            # Store status separately for quick lookup
            await self.redis.set_cache(
                f"{self.status_key}:{queue_id}",
                {
                    'status': 'queued',
                    'created_at': queue_item['created_at'],
                    'last_updated': datetime.now().isoformat()
                }
            )
            
            logger.info("Ticket added to queue", queue_id=queue_id, subject=ticket_request.subject)
            return queue_id
            
        except Exception as e:
            logger.error("Failed to add ticket to queue", error=str(e))
            raise
    
    async def get_ticket_status(self, queue_id: str) -> Dict:
        """Get status of a queued ticket"""
        try:
            status = await self.redis.get_cache(f"{self.status_key}:{queue_id}")
            
            if not status:
                return {
                    'status': 'not_found',
                    'last_updated': datetime.now().isoformat()
                }
            
            return status
            
        except Exception as e:
            logger.error("Failed to get ticket status", error=str(e), queue_id=queue_id)
            return {
                'status': 'error',
                'last_updated': datetime.now().isoformat()
            }
    
    async def process_queue(self) -> int:
        """Process pending tickets in the queue"""
        processed_count = 0
        
        try:
            while True:
                # Get next item from queue
                item_json = await self.redis.redis.rpop(self.queue_key)
                if not item_json:
                    break
                
                queue_item = json.loads(item_json)
                queue_id = queue_item['id']
                
                try:
                    # Try to process the ticket
                    from .zoho_client import ZohoClient
                    from ..models.schemas import TicketRequest
                    
                    zoho_client = ZohoClient()
                    await zoho_client.initialize()
                    
                    # Reconstruct ticket request
                    ticket_data = queue_item['ticket_data']
                    ticket_request = TicketRequest(**ticket_data)
                    
                    # Create ticket in Zoho
                    ticket_id = await zoho_client.create_ticket(ticket_request)
                    
                    # Update status to completed
                    await self.redis.set_cache(
                        f"{self.status_key}:{queue_id}",
                        {
                            'status': 'completed',
                            'ticket_id': ticket_id,
                            'created_at': queue_item['created_at'],
                            'last_updated': datetime.now().isoformat()
                        }
                    )
                    
                    # Publish success event
                    await self.redis.publish("tickets:created", {
                        "ticket_id": ticket_id,
                        "queue_id": queue_id,
                        "subject": ticket_request.subject,
                        "priority": ticket_request.priority.value,
                        "contact_id": ticket_request.contact_id
                    })
                    
                    processed_count += 1
                    logger.info("Queued ticket processed", queue_id=queue_id, ticket_id=ticket_id)
                    
                except Exception as process_error:
                    # Increment attempts
                    queue_item['attempts'] += 1
                    queue_item['error'] = str(process_error)
                    queue_item['last_attempt'] = datetime.now().isoformat()
                    
                    if queue_item['attempts'] < queue_item['max_attempts']:
                        # Re-queue for retry
                        await self.redis.redis.lpush(self.queue_key, json.dumps(queue_item))
                        
                        # Update status
                        await self.redis.set_cache(
                            f"{self.status_key}:{queue_id}",
                            {
                                'status': 'retrying',
                                'attempts': queue_item['attempts'],
                                'error': str(process_error),
                                'created_at': queue_item['created_at'],
                                'last_updated': datetime.now().isoformat()
                            }
                        )
                        
                        logger.warning(
                            "Ticket processing failed, retrying",
                            queue_id=queue_id,
                            attempts=queue_item['attempts'],
                            error=str(process_error)
                        )
                    else:
                        # Max attempts reached, mark as failed
                        await self.redis.set_cache(
                            f"{self.status_key}:{queue_id}",
                            {
                                'status': 'failed',
                                'attempts': queue_item['attempts'],
                                'error': str(process_error),
                                'created_at': queue_item['created_at'],
                                'last_updated': datetime.now().isoformat()
                            }
                        )
                        
                        logger.error(
                            "Ticket processing failed permanently",
                            queue_id=queue_id,
                            attempts=queue_item['attempts'],
                            error=str(process_error)
                        )
            
            if processed_count > 0:
                logger.info("Queue processing completed", processed_count=processed_count)
            
            return processed_count
            
        except Exception as e:
            logger.error("Failed to process queue", error=str(e))
            raise
    
    async def get_queue_stats(self) -> Dict:
        """Get queue statistics"""
        try:
            queue_length = await self.redis.redis.llen(self.queue_key)
            
            return {
                'queue_length': queue_length,
                'last_check': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error("Failed to get queue stats", error=str(e))
            return {
                'queue_length': -1,
                'error': str(e),
                'last_check': datetime.now().isoformat()
            }
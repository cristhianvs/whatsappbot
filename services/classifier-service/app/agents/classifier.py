from typing import Dict, List
import os
from langchain.agents import Agent
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage
import structlog

from ..models.schemas import ClassificationResponse

logger = structlog.get_logger()

class MessageClassifier:
    def __init__(self):
        self.llm = ChatOpenAI(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            api_key=os.getenv("OPENAI_API_KEY"),
            temperature=0.1
        )
        
        self.system_prompt = """You are a message classifier for a retail support system.
        
        Your task is to analyze WhatsApp messages and determine if they represent support incidents.
        
        RETAIL CONTEXT:
        - This is for retail stores and POS systems
        - Common issues: store closures, POS failures, inventory problems, payment issues
        - Urgent keywords: "urgente", "no funciona", "cerrado", "sistema caído", "no pueden vender"
        
        CLASSIFICATION CRITERIA:
        - IS INCIDENT: Clear technical/operational problems affecting business operations
        - NOT INCIDENT: General questions, casual conversation, already resolved issues
        
        PRIORITY LEVELS:
        - urgent: Store cannot operate, system down, prevents sales
        - normal: Issues that need attention but don't stop operations
        - low: General questions or minor issues
        
        CATEGORIES:
        - technical: POS, system, software issues
        - operational: Store operations, inventory, processes
        - urgent: Any critical issue requiring immediate attention
        - general: Questions, information requests
        
        Return a JSON response with:
        - is_incident: boolean
        - confidence: float (0.0-1.0)
        - category: string
        - trigger_words: array of detected keywords
        - priority: string
        - requires_human: boolean (for complex cases)
        """
    
    async def classify(self, text: str, context: Dict = None) -> ClassificationResponse:
        try:
            messages = [
                SystemMessage(content=self.system_prompt),
                HumanMessage(content=f"Classify this message: '{text}'")
            ]
            
            if context:
                messages.append(HumanMessage(content=f"Additional context: {context}"))
            
            response = await self.llm.ainvoke(messages)
            
            # Parse the LLM response and extract classification data
            result = self._parse_classification_response(response.content, text)
            
            logger.info(
                "Message classified",
                text=text[:100],
                is_incident=result.is_incident,
                confidence=result.confidence,
                category=result.category
            )
            
            return result
            
        except Exception as e:
            logger.error("Classification failed", error=str(e))
            # Return safe default
            return ClassificationResponse(
                is_incident=False,
                confidence=0.0,
                category="general",
                trigger_words=[],
                priority="low",
                requires_human=True
            )
    
    def _parse_classification_response(self, response: str, original_text: str) -> ClassificationResponse:
        # Simple keyword-based fallback if LLM response parsing fails
        text_lower = original_text.lower()
        
        urgent_keywords = ["urgente", "no funciona", "cerrado", "sistema caído", "no pueden vender", "error"]
        technical_keywords = ["pos", "sistema", "software", "aplicación", "red", "internet"]
        operational_keywords = ["tienda", "inventario", "producto", "cliente", "venta"]
        
        # Detect trigger words
        trigger_words = []
        for keyword in urgent_keywords + technical_keywords + operational_keywords:
            if keyword in text_lower:
                trigger_words.append(keyword)
        
        # Determine if it's an incident
        is_incident = any(keyword in text_lower for keyword in urgent_keywords + ["problema", "ayuda", "falla"])
        
        # Determine category
        if any(keyword in text_lower for keyword in urgent_keywords):
            category = "urgent"
            priority = "urgent"
        elif any(keyword in text_lower for keyword in technical_keywords):
            category = "technical"
            priority = "normal"
        elif any(keyword in text_lower for keyword in operational_keywords):
            category = "operational"
            priority = "normal"
        else:
            category = "general"
            priority = "low"
        
        # Calculate confidence based on trigger words found
        confidence = min(0.9, len(trigger_words) * 0.3) if is_incident else 0.1
        
        return ClassificationResponse(
            is_incident=is_incident,
            confidence=confidence,
            category=category,
            trigger_words=trigger_words,
            priority=priority,
            requires_human=confidence < 0.5
        )
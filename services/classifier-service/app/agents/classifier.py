from typing import Dict, List, Any
import structlog
import asyncio

from ..models.schemas import ClassificationResponse, MessageContext
from ..ai.model_manager import model_manager

logger = structlog.get_logger()

class MessageClassifier:
    def __init__(self):
        self.fallback_keywords = {
            "urgent": ["urgente", "no funciona", "cerrado", "sistema caído", "no pueden vender", "error", "crítico"],
            "technical": ["pos", "sistema", "software", "aplicación", "red", "internet", "servidor", "base de datos"],
            "operational": ["tienda", "inventario", "producto", "cliente", "venta", "caja", "personal"],
            "billing": ["factura", "cobro", "pago", "precio", "descuento", "promoción"],
            "general": ["pregunta", "consulta", "información", "horario", "ubicación"]
        }
    
    async def classify(self, text: str, context: MessageContext = None) -> ClassificationResponse:
        """
        Classify a message using AI models with fallback to keyword-based classification
        """
        try:
            # Prepare context for AI model
            ai_context = {}
            if context:
                ai_context = {
                    "message_id": context.message_id,
                    "sender": context.sender,
                    "timestamp": context.timestamp.isoformat() if context.timestamp else None,
                    "group_id": context.group_id,
                    "has_media": context.has_media,
                    "message_type": context.message_type
                }
            
            # Call AI model for classification
            ai_result = await model_manager.classify_message(text, ai_context)
            
            # Convert AI result to our schema
            result = self._convert_ai_result(ai_result, text)
            
            logger.info(
                "Message classified with AI",
                text=text[:100],
                is_incident=result.is_support_incident,
                confidence=result.confidence,
                category=result.category
            )
            
            return result
            
        except Exception as e:
            logger.warning("AI classification failed, using fallback", error=str(e))
            # Fallback to keyword-based classification
            return self._fallback_classification(text)
    
    def _convert_ai_result(self, ai_result: Dict[str, Any], original_text: str) -> ClassificationResponse:
        """Convert AI model result to our response schema"""
        try:
            return ClassificationResponse(
                is_support_incident=ai_result.get("is_support_incident", False),
                confidence=float(ai_result.get("confidence", 0.0)),
                category=ai_result.get("category", "general_inquiry"),
                urgency=ai_result.get("urgency", "low"),
                summary=ai_result.get("summary", ""),
                requires_followup=ai_result.get("requires_followup", True),
                suggested_response=ai_result.get("suggested_response", ""),
                extracted_info=ai_result.get("extracted_info", {}),
                trigger_words=self._extract_trigger_words(original_text),
                processing_time=0.0  # Will be set by the caller
            )
        except Exception as e:
            logger.error("Failed to convert AI result", error=str(e), ai_result=ai_result)
            return self._fallback_classification(original_text)
    
    def _fallback_classification(self, text: str) -> ClassificationResponse:
        """Keyword-based fallback classification when AI fails"""
        text_lower = text.lower()
        
        # Detect trigger words
        trigger_words = self._extract_trigger_words(text)
        
        # Determine if it's a support incident
        incident_indicators = (
            self.fallback_keywords["urgent"] + 
            ["problema", "ayuda", "falla", "no puede", "error", "roto"]
        )
        is_incident = any(keyword in text_lower for keyword in incident_indicators)
        
        # Determine category and urgency
        category = "not_support"
        urgency = "low"
        
        if any(keyword in text_lower for keyword in self.fallback_keywords["urgent"]):
            category = "technical"
            urgency = "critical"
        elif any(keyword in text_lower for keyword in self.fallback_keywords["technical"]):
            category = "technical"
            urgency = "medium"
        elif any(keyword in text_lower for keyword in self.fallback_keywords["billing"]):
            category = "billing"
            urgency = "medium"
        elif any(keyword in text_lower for keyword in self.fallback_keywords["operational"]):
            category = "general_inquiry"
            urgency = "low"
        elif is_incident:
            category = "technical"
            urgency = "medium"
        
        # Calculate confidence based on trigger words
        confidence = min(0.8, len(trigger_words) * 0.2) if is_incident else 0.3
        
        # Generate basic response
        if is_incident:
            suggested_response = "Hemos recibido tu reporte y será atendido por nuestro equipo técnico. Te mantendremos informado del progreso."
        else:
            suggested_response = "Gracias por tu mensaje. ¿En qué podemos ayudarte?"
            
        return ClassificationResponse(
            is_support_incident=is_incident,
            confidence=confidence,
            category=category,
            urgency=urgency,
            summary=f"Mensaje clasificado por palabras clave: {', '.join(trigger_words[:3])}" if trigger_words else "Mensaje general",
            requires_followup=confidence < 0.6,
            suggested_response=suggested_response,
            extracted_info={
                "classification_method": "keyword_fallback",
                "trigger_words_count": len(trigger_words)
            },
            trigger_words=trigger_words,
            processing_time=0.0
        )
    
    def _extract_trigger_words(self, text: str) -> List[str]:
        """Extract relevant trigger words from text"""
        text_lower = text.lower()
        found_words = []
        
        for category, keywords in self.fallback_keywords.items():
            for keyword in keywords:
                if keyword in text_lower:
                    found_words.append(keyword)
        
        return list(set(found_words))  # Remove duplicates

# Global instance
classifier = MessageClassifier()
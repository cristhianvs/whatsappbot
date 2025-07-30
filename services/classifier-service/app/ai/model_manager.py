import asyncio
import json
import os
from typing import Dict, Any, Optional, List
from enum import Enum
import structlog
import aiohttp
from openai import AsyncOpenAI
import google.generativeai as genai

logger = structlog.get_logger()

class ModelProvider(Enum):
    OPENAI = "openai"
    GOOGLE = "google"
    ANTHROPIC = "anthropic"

class AIModelManager:
    def __init__(self):
        self.primary_model = ModelProvider(os.getenv('PRIMARY_AI_MODEL', 'openai'))
        self.fallback_model = ModelProvider(os.getenv('FALLBACK_AI_MODEL', 'google'))
        self.temperature = float(os.getenv('MODEL_TEMPERATURE', '0.1'))
        self.max_tokens = int(os.getenv('MAX_TOKENS', '1000'))
        
        # Initialize clients
        self.openai_client = None
        self.google_client = None
        self.anthropic_client = None
        
        self._initialize_clients()
    
    def _initialize_clients(self):
        """Initialize available AI model clients"""
        try:
            # OpenAI
            openai_key = os.getenv('OPENAI_API_KEY')
            if openai_key:
                self.openai_client = AsyncOpenAI(api_key=openai_key)
                logger.info("OpenAI client initialized")
            
            # Google Gemini
            google_key = os.getenv('GOOGLE_API_KEY')
            if google_key:
                genai.configure(api_key=google_key)
                self.google_client = genai.GenerativeModel('gemini-pro')
                logger.info("Google Gemini client initialized")
            
            # Anthropic Claude
            anthropic_key = os.getenv('ANTHROPIC_API_KEY')
            if anthropic_key:
                # Note: Using HTTP client for Anthropic as their SDK might not be async
                self.anthropic_client = anthropic_key
                logger.info("Anthropic client configured")
                
        except Exception as e:
            logger.error("Failed to initialize AI clients", error=str(e))
    
    async def classify_message(self, message_text: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Classify if a message is a support incident and extract relevant information
        """
        prompt = self._build_classification_prompt(message_text, context)
        
        # Try primary model first
        try:
            result = await self._call_model(self.primary_model, prompt)
            if result:
                logger.info("Message classified successfully", model=self.primary_model.value)
                return result
        except Exception as e:
            logger.warning("Primary model failed, trying fallback", 
                         primary=self.primary_model.value, error=str(e))
        
        # Try fallback model
        try:
            result = await self._call_model(self.fallback_model, prompt)
            if result:
                logger.info("Message classified with fallback", model=self.fallback_model.value)
                return result
        except Exception as e:
            logger.error("All models failed for classification", error=str(e))
        
        # Return default classification if all models fail
        return self._default_classification()
    
    def _build_classification_prompt(self, message_text: str, context: Dict[str, Any] = None) -> str:
        """Build the classification prompt"""
        prompt = f"""
Analyze the following WhatsApp message and determine if it represents a technical support incident that requires assistance.

Message: "{message_text}"

Context: {json.dumps(context or {}, indent=2)}

Classify this message and respond with a JSON object containing:

{{
    "is_support_incident": boolean,
    "confidence": float (0.0 to 1.0),
    "category": string ("technical", "billing", "general_inquiry", "complaint", "compliment", "not_support"),
    "urgency": string ("low", "medium", "high", "critical"),
    "summary": string (brief summary of the issue),
    "requires_followup": boolean,
    "suggested_response": string (suggested initial response),
    "extracted_info": {{
        "user_type": string ("customer", "potential_customer", "internal", "unknown"),
        "product_mentioned": string or null,
        "error_code": string or null,
        "contact_info": string or null
    }}
}}

Guidelines:
- is_support_incident: true if this needs technical support attention
- confidence: how certain you are about the classification
- category: the type of support request
- urgency: based on business impact and tone
- summary: concise description in Spanish
- requires_followup: true if more information is needed
- suggested_response: appropriate initial response in Spanish
- extracted_info: any relevant details found in the message

Respond only with valid JSON.
"""
        return prompt
    
    async def _call_model(self, provider: ModelProvider, prompt: str) -> Optional[Dict[str, Any]]:
        """Call specific AI model provider"""
        try:
            if provider == ModelProvider.OPENAI and self.openai_client:
                return await self._call_openai(prompt)
            elif provider == ModelProvider.GOOGLE and self.google_client:
                return await self._call_google(prompt)
            elif provider == ModelProvider.ANTHROPIC and self.anthropic_client:
                return await self._call_anthropic(prompt)
            else:
                logger.warning("Model provider not available", provider=provider.value)
                return None
        except Exception as e:
            logger.error("Model call failed", provider=provider.value, error=str(e))
            raise
    
    async def _call_openai(self, prompt: str) -> Dict[str, Any]:
        """Call OpenAI API"""
        model_name = os.getenv('MODEL_NAME', 'gpt-4o-mini')
        
        response = await self.openai_client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "You are an expert support ticket classifier. Always respond with valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            response_format={"type": "json_object"}
        )
        
        content = response.choices[0].message.content
        return json.loads(content)
    
    async def _call_google(self, prompt: str) -> Dict[str, Any]:
        """Call Google Gemini API"""
        # Note: This is a simplified implementation
        # In production, you'd want to use async version
        response = await asyncio.get_event_loop().run_in_executor(
            None, 
            lambda: self.google_client.generate_content(
                f"Respond only with valid JSON. {prompt}"
            )
        )
        
        content = response.text
        return json.loads(content)
    
    async def _call_anthropic(self, prompt: str) -> Dict[str, Any]:
        """Call Anthropic Claude API"""
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.anthropic_client,
            "anthropic-version": "2023-06-01"
        }
        
        data = {
            "model": "claude-3-haiku-20240307",
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "messages": [
                {
                    "role": "user",
                    "content": f"Respond only with valid JSON. {prompt}"
                }
            ]
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=data
            ) as response:
                result = await response.json()
                content = result["content"][0]["text"]
                return json.loads(content)
    
    def _default_classification(self) -> Dict[str, Any]:
        """Return default classification when all models fail"""
        return {
            "is_support_incident": True,  # Conservative approach
            "confidence": 0.1,
            "category": "general_inquiry",
            "urgency": "medium",
            "summary": "Mensaje requiere revisión manual",
            "requires_followup": True,
            "suggested_response": "Hola, hemos recibido tu mensaje y será revisado por nuestro equipo de soporte. Te responderemos a la brevedad.",
            "extracted_info": {
                "user_type": "unknown",
                "product_mentioned": None,
                "error_code": None,
                "contact_info": None
            }
        }

# Global instance
model_manager = AIModelManager()
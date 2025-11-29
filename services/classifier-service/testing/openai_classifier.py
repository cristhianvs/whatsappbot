"""
OpenAI GPT-4o-mini Classifier
Clasifica mensajes de WhatsApp como incidencias técnicas
"""
from openai import OpenAI
import json
import os
from pathlib import Path
from typing import Dict, Any
import time

class OpenAIClassifier:
    def __init__(self, api_key: str = None):
        """
        Inicializa el clasificador con GPT-4o-mini

        Args:
            api_key: API key de OpenAI (si no se proporciona, lee de env)
        """
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY no encontrada")

        self.client = OpenAI(api_key=self.api_key)
        self.model = "gpt-4o-mini"

        # Cargar prompt desde archivo
        prompts_dir = Path(__file__).parent / "prompts"
        prompt_file = prompts_dir / "incident_classifier.txt"

        with open(prompt_file, 'r', encoding='utf-8') as f:
            self.system_prompt = f.read()

    def classify(self, mensaje: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Clasifica un mensaje como incidencia o no

        Args:
            mensaje: Texto del mensaje de WhatsApp
            metadata: Metadata adicional (usuario, timestamp, etc.)

        Returns:
            Dict con clasificación, confianza, categoría, etc.
        """
        start_time = time.time()

        try:
            # Preparar el mensaje de usuario
            user_message = f"Mensaje a clasificar:\n\n{mensaje}"

            # Llamar a OpenAI
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": self.system_prompt
                    },
                    {
                        "role": "user",
                        "content": user_message
                    }
                ],
                temperature=0.1,  # Baja temperatura para respuestas consistentes
                max_tokens=1000,
                response_format={"type": "json_object"}  # Forzar respuesta JSON
            )

            # Extraer respuesta
            response_text = response.choices[0].message.content

            # Parsear JSON
            result = json.loads(response_text)

            # Agregar metadata
            elapsed_time = (time.time() - start_time) * 1000  # en ms

            result['_metadata'] = {
                'modelo': self.model,
                'tiempo_ms': round(elapsed_time, 2),
                'tokens_input': response.usage.prompt_tokens,
                'tokens_output': response.usage.completion_tokens,
                'costo_estimado_usd': self._calcular_costo(
                    response.usage.prompt_tokens,
                    response.usage.completion_tokens
                )
            }

            return result

        except json.JSONDecodeError as e:
            # Si falla el parseo JSON, devolver error pero con formato consistente
            elapsed_time = (time.time() - start_time) * 1000
            return {
                'es_incidencia': None,
                'confianza': 0.0,
                'razonamiento': f'Error al parsear respuesta JSON: {str(e)}',
                'categoria': None,
                'prioridad': None,
                'metadata': {},
                '_metadata': {
                    'modelo': self.model,
                    'tiempo_ms': round(elapsed_time, 2),
                    'error': str(e),
                    'raw_response': response_text[:500]  # Primeros 500 chars
                }
            }

        except Exception as e:
            elapsed_time = (time.time() - start_time) * 1000
            return {
                'es_incidencia': None,
                'confianza': 0.0,
                'razonamiento': f'Error en clasificación: {str(e)}',
                'categoria': None,
                'prioridad': None,
                'metadata': {},
                '_metadata': {
                    'modelo': self.model,
                    'tiempo_ms': round(elapsed_time, 2),
                    'error': str(e)
                }
            }

    def _calcular_costo(self, input_tokens: int, output_tokens: int) -> float:
        """
        Calcula el costo estimado de la llamada

        GPT-4o-mini pricing:
        - Input: $0.150 / 1M tokens
        - Output: $0.600 / 1M tokens
        """
        input_cost = (input_tokens / 1_000_000) * 0.150
        output_cost = (output_tokens / 1_000_000) * 0.600
        return round(input_cost + output_cost, 6)

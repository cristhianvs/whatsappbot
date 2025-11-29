"""
Claude Sonnet 4.5 Classifier
Clasifica mensajes de WhatsApp como incidencias técnicas
"""
import anthropic
import json
import os
from pathlib import Path
from typing import Dict, Any
import time

class ClaudeClassifier:
    def __init__(self, api_key: str = None):
        """
        Inicializa el clasificador con Claude Sonnet 4.5

        Args:
            api_key: API key de Anthropic (si no se proporciona, lee de env)
        """
        self.api_key = api_key or os.getenv('ANTHROPIC_API_KEY')
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY no encontrada")

        self.client = anthropic.Anthropic(api_key=self.api_key)
        self.model = "claude-sonnet-4-20250514"  # Claude Sonnet 4.5

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

            # Llamar a Claude
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1000,
                temperature=0.1,  # Baja temperatura para respuestas consistentes
                system=self.system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": user_message
                    }
                ]
            )

            # Extraer respuesta
            response_text = response.content[0].text

            # Parsear JSON
            # Claude puede envolver el JSON en ```json ... ```, así que lo limpiamos
            response_text = response_text.strip()
            if response_text.startswith('```json'):
                response_text = response_text[7:]  # Quitar ```json
            if response_text.endswith('```'):
                response_text = response_text[:-3]  # Quitar ```
            response_text = response_text.strip()

            result = json.loads(response_text)

            # Agregar metadata
            elapsed_time = (time.time() - start_time) * 1000  # en ms

            result['_metadata'] = {
                'modelo': self.model,
                'tiempo_ms': round(elapsed_time, 2),
                'tokens_input': response.usage.input_tokens,
                'tokens_output': response.usage.output_tokens,
                'costo_estimado_usd': self._calcular_costo(
                    response.usage.input_tokens,
                    response.usage.output_tokens
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

        Claude Sonnet 4.5 pricing:
        - Input: $3.00 / 1M tokens
        - Output: $15.00 / 1M tokens
        """
        input_cost = (input_tokens / 1_000_000) * 3.00
        output_cost = (output_tokens / 1_000_000) * 15.00
        return round(input_cost + output_cost, 6)

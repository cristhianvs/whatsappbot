"""
Sistema de Voting/Consensus
Combina las respuestas de Claude y OpenAI para determinar clasificación final
"""
from typing import Dict, Any, List

class VotingSystem:
    """
    Sistema que combina clasificaciones de múltiples modelos
    usando estrategia de consenso y confianza ponderada
    """

    @staticmethod
    def consensus(claude_result: Dict[str, Any], openai_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Determina clasificación final basada en consenso entre modelos

        Args:
            claude_result: Resultado de Claude classifier
            openai_result: Resultado de OpenAI classifier

        Returns:
            Clasificación consensuada con metadata de comparación
        """
        # Extraer decisiones y confianzas
        claude_es_inc = claude_result.get('es_incidencia')
        openai_es_inc = openai_result.get('es_incidencia')

        claude_conf = claude_result.get('confianza', 0.0)
        openai_conf = openai_result.get('confianza', 0.0)

        # CASO 1: Ambos coinciden que SÍ es incidencia
        if claude_es_inc is True and openai_es_inc is True:
            return VotingSystem._caso_ambos_si(claude_result, openai_result)

        # CASO 2: Ambos coinciden que NO es incidencia
        if claude_es_inc is False and openai_es_inc is False:
            return VotingSystem._caso_ambos_no(claude_result, openai_result)

        # CASO 3: Discrepancia - uno dice SÍ y otro NO
        if claude_es_inc is not None and openai_es_inc is not None:
            if claude_es_inc != openai_es_inc:
                return VotingSystem._caso_discrepancia(claude_result, openai_result)

        # CASO 4: Alguno tuvo error (None)
        return VotingSystem._caso_error(claude_result, openai_result)

    @staticmethod
    def _caso_ambos_si(claude_result: Dict, openai_result: Dict) -> Dict:
        """Ambos modelos coinciden: SÍ es incidencia"""
        claude_conf = claude_result.get('confianza', 0.0)
        openai_conf = openai_result.get('confianza', 0.0)

        # Promedio de confianzas + bonus por consenso
        confianza_promedio = (claude_conf + openai_conf) / 2
        confianza_final = min(confianza_promedio * 1.1, 1.0)  # Bonus 10%, max 1.0

        # Elegir categoría y prioridad (preferir la de mayor confianza)
        if claude_conf >= openai_conf:
            categoria = claude_result.get('categoria')
            prioridad = claude_result.get('prioridad')
            metadata = claude_result.get('metadata', {})
        else:
            categoria = openai_result.get('categoria')
            prioridad = openai_result.get('prioridad')
            metadata = openai_result.get('metadata', {})

        return {
            'es_incidencia': True,
            'confianza': round(confianza_final, 3),
            'categoria': categoria,
            'prioridad': prioridad,
            'metadata': metadata,
            'consenso': {
                'tipo': 'ambos_si',
                'modelos_acuerdo': ['claude', 'openai'],
                'modelo_primario': 'claude' if claude_conf >= openai_conf else 'openai',
                'requiere_revision': False
            },
            'comparacion': VotingSystem._generar_comparacion(claude_result, openai_result)
        }

    @staticmethod
    def _caso_ambos_no(claude_result: Dict, openai_result: Dict) -> Dict:
        """Ambos modelos coinciden: NO es incidencia"""
        claude_conf = claude_result.get('confianza', 0.0)
        openai_conf = openai_result.get('confianza', 0.0)

        # Confianza muy alta cuando ambos están seguros que NO es
        confianza_final = max(claude_conf, openai_conf)

        return {
            'es_incidencia': False,
            'confianza': round(confianza_final, 3),
            'categoria': None,
            'prioridad': None,
            'metadata': {},
            'consenso': {
                'tipo': 'ambos_no',
                'modelos_acuerdo': ['claude', 'openai'],
                'modelo_primario': 'consensus',
                'requiere_revision': False
            },
            'comparacion': VotingSystem._generar_comparacion(claude_result, openai_result)
        }

    @staticmethod
    def _caso_discrepancia(claude_result: Dict, openai_result: Dict) -> Dict:
        """Discrepancia: uno dice SÍ y otro NO"""
        claude_conf = claude_result.get('confianza', 0.0)
        openai_conf = openai_result.get('confianza', 0.0)
        claude_es_inc = claude_result.get('es_incidencia')

        # Usar el modelo con mayor confianza
        if claude_conf > openai_conf:
            resultado_primario = claude_result
            modelo_primario = 'claude'
        else:
            resultado_primario = openai_result
            modelo_primario = 'openai'

        # Penalización por discrepancia (reduce confianza 15%)
        confianza_final = resultado_primario.get('confianza', 0.0) * 0.85

        return {
            'es_incidencia': resultado_primario.get('es_incidencia'),
            'confianza': round(confianza_final, 3),
            'categoria': resultado_primario.get('categoria'),
            'prioridad': resultado_primario.get('prioridad'),
            'metadata': resultado_primario.get('metadata', {}),
            'consenso': {
                'tipo': 'discrepancia',
                'modelos_acuerdo': [modelo_primario],
                'modelo_primario': modelo_primario,
                'requiere_revision': True,  # Marcar para revisión humana
                'razon_discrepancia': f"Claude dice {claude_es_inc}, OpenAI dice {not claude_es_inc}"
            },
            'comparacion': VotingSystem._generar_comparacion(claude_result, openai_result)
        }

    @staticmethod
    def _caso_error(claude_result: Dict, openai_result: Dict) -> Dict:
        """Alguno de los modelos tuvo un error"""
        # Usar el que no tuvo error
        if claude_result.get('es_incidencia') is not None:
            resultado_valido = claude_result
            modelo_valido = 'claude'
        elif openai_result.get('es_incidencia') is not None:
            resultado_valido = openai_result
            modelo_valido = 'openai'
        else:
            # Ambos fallaron
            return {
                'es_incidencia': None,
                'confianza': 0.0,
                'categoria': None,
                'prioridad': None,
                'metadata': {},
                'consenso': {
                    'tipo': 'error_ambos',
                    'modelos_acuerdo': [],
                    'modelo_primario': None,
                    'requiere_revision': True
                },
                'comparacion': VotingSystem._generar_comparacion(claude_result, openai_result)
            }

        # Penalización por falta de consenso
        confianza_final = resultado_valido.get('confianza', 0.0) * 0.75

        return {
            'es_incidencia': resultado_valido.get('es_incidencia'),
            'confianza': round(confianza_final, 3),
            'categoria': resultado_valido.get('categoria'),
            'prioridad': resultado_valido.get('prioridad'),
            'metadata': resultado_valido.get('metadata', {}),
            'consenso': {
                'tipo': 'error_parcial',
                'modelos_acuerdo': [modelo_valido],
                'modelo_primario': modelo_valido,
                'requiere_revision': True,
                'modelo_con_error': 'openai' if modelo_valido == 'claude' else 'claude'
            },
            'comparacion': VotingSystem._generar_comparacion(claude_result, openai_result)
        }

    @staticmethod
    def _generar_comparacion(claude_result: Dict, openai_result: Dict) -> Dict:
        """Genera metadata de comparación entre ambos modelos"""
        comparacion = {
            'claude': {
                'es_incidencia': claude_result.get('es_incidencia'),
                'confianza': claude_result.get('confianza'),
                'categoria': claude_result.get('categoria'),
                'prioridad': claude_result.get('prioridad'),
                'tiempo_ms': claude_result.get('_metadata', {}).get('tiempo_ms'),
                'costo_usd': claude_result.get('_metadata', {}).get('costo_estimado_usd')
            },
            'openai': {
                'es_incidencia': openai_result.get('es_incidencia'),
                'confianza': openai_result.get('confianza'),
                'categoria': openai_result.get('categoria'),
                'prioridad': openai_result.get('prioridad'),
                'tiempo_ms': openai_result.get('_metadata', {}).get('tiempo_ms'),
                'costo_usd': openai_result.get('_metadata', {}).get('costo_estimado_usd')
            }
        }

        # Identificar diferencias
        diferencias = []
        coincidencias = []

        if claude_result.get('es_incidencia') == openai_result.get('es_incidencia'):
            coincidencias.append('Ambos coinciden en clasificación (sí/no incidencia)')
        else:
            diferencias.append(f"Clasificación: Claude={claude_result.get('es_incidencia')}, OpenAI={openai_result.get('es_incidencia')}")

        if claude_result.get('categoria') == openai_result.get('categoria'):
            if claude_result.get('categoria') is not None:
                coincidencias.append(f"Misma categoría: {claude_result.get('categoria')}")
        else:
            if claude_result.get('categoria') and openai_result.get('categoria'):
                diferencias.append(f"Categoría: Claude={claude_result.get('categoria')}, OpenAI={openai_result.get('categoria')}")

        if claude_result.get('prioridad') == openai_result.get('prioridad'):
            if claude_result.get('prioridad') is not None:
                coincidencias.append(f"Misma prioridad: {claude_result.get('prioridad')}")
        else:
            if claude_result.get('prioridad') and openai_result.get('prioridad'):
                diferencias.append(f"Prioridad: Claude={claude_result.get('prioridad')}, OpenAI={openai_result.get('prioridad')}")

        comparacion['diferencias'] = diferencias
        comparacion['coincidencias'] = coincidencias

        return comparacion

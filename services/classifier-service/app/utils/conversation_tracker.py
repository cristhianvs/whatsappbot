"""
Conversation Tracker - Gestiona hilos de conversación para evitar tickets duplicados
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import json
import re
import structlog

logger = structlog.get_logger()


class ConversationTracker:
    """
    Gestiona hilos de conversación para asociar mensajes relacionados
    y evitar crear tickets duplicados sobre la misma incidencia.

    Estrategia multi-capa:
    1. Detectar mensajes citados del bot (contienen Ticket ID)
    2. Buscar incidencias recientes del mismo grupo (ventana temporal)
    3. Análisis de similitud opcional
    """

    def __init__(self, redis_client, bot_phone_number: str = "5215530482752"):
        """
        Args:
            redis_client: Cliente Redis (app.utils.redis_client.RedisClient)
            bot_phone_number: Número de teléfono del bot (sin @s.whatsapp.net)
        """
        self.redis = redis_client
        self.bot_number = bot_phone_number

        # Configuración
        self.INCIDENT_TTL = 7200  # 2 horas de ventana activa
        self.TICKET_PREFIX = "incident:active:"
        self.THREAD_PREFIX = "thread:"

    async def check_existing_incident(self, message_data: Dict) -> Optional[str]:
        """
        Verifica si el mensaje es parte de una incidencia existente

        Args:
            message_data: Diccionario con datos del mensaje (puede ser dict o MessageData)

        Returns:
            ticket_id si existe incidencia relacionada, None si es nueva
        """
        try:
            # Convertir MessageData a dict si es necesario
            if hasattr(message_data, 'model_dump'):
                message_dict = message_data.model_dump()
            else:
                message_dict = message_data

            # MÉTODO 1: Mensaje cita respuesta del bot con ticket ID
            if message_dict.get('quoted_message'):
                ticket_id = await self._extract_ticket_from_quoted(message_dict)
                if ticket_id:
                    logger.info("Found ticket from quoted message",
                               ticket_id=ticket_id,
                               message_id=message_dict.get('id'))
                    return ticket_id

            # MÉTODO 2: Buscar incidencias recientes del mismo grupo
            ticket_id = await self._find_recent_incident(message_dict)
            if ticket_id:
                logger.info("Found ticket from recent incident",
                           ticket_id=ticket_id,
                           message_id=message_dict.get('id'))
                return ticket_id

            # No hay incidencia relacionada
            return None

        except Exception as e:
            logger.error("Error checking existing incident",
                        error=str(e),
                        message_id=message_dict.get('id'))
            return None

    async def _extract_ticket_from_quoted(self, message_data: Dict) -> Optional[str]:
        """
        Extrae ticket ID del mensaje citado si es del bot

        Args:
            message_data: Datos del mensaje

        Returns:
            ticket_id si se encontró, None si no
        """
        try:
            quoted = message_data.get('quoted_message')
            if not quoted:
                return None

            # Obtener datos del mensaje citado
            if isinstance(quoted, dict):
                quoted_text = quoted.get('text', '')
                quoted_participant = quoted.get('participant', '')
            else:
                # Es un objeto QuotedMessage
                quoted_text = quoted.text if hasattr(quoted, 'text') else ''
                quoted_participant = quoted.participant if hasattr(quoted, 'participant') else ''

            # Verificar si el mensaje citado es del bot
            if self.bot_number not in quoted_participant:
                logger.debug("Quoted message not from bot",
                           quoted_participant=quoted_participant,
                           bot_number=self.bot_number)
                return None

            # Buscar patrón de ticket en el texto citado
            # Soporta: "Ticket #12345", "Ticket 12345", "#12345"
            patterns = [
                r'Ticket #(\d+)',
                r'Ticket (\d+)',
                r'ticket #(\d+)',
                r'ticket (\d+)',
                r'#(\d+)'
            ]

            for pattern in patterns:
                match = re.search(pattern, quoted_text)
                if match:
                    ticket_id = match.group(1)

                    # Verificar que el ticket sigue activo en Redis
                    is_active = await self.is_ticket_active(ticket_id)
                    if is_active:
                        logger.info("Extracted ticket from quoted message",
                                   ticket_id=ticket_id,
                                   quoted_text=quoted_text[:100])
                        return ticket_id
                    else:
                        logger.debug("Ticket found but not active",
                                    ticket_id=ticket_id)

            return None

        except Exception as e:
            logger.error("Error extracting ticket from quoted message",
                        error=str(e))
            return None

    async def _find_recent_incident(self, message_data: Dict) -> Optional[str]:
        """
        Busca incidencias recientes del mismo contexto (grupo/usuario)

        Args:
            message_data: Datos del mensaje

        Returns:
            ticket_id si se encontró incidencia reciente, None si no
        """
        try:
            # Identificar el contexto (grupo o chat individual)
            group_id = message_data.get('group_id') or message_data.get('from_user')
            if not group_id:
                return None

            # Buscar en Redis incidencias activas de este contexto
            pattern = f"{self.TICKET_PREFIX}{group_id}:*"

            # Usar scan en lugar de keys para mejor performance
            keys = await self._scan_keys(pattern)

            if not keys:
                return None

            # Obtener todas las incidencias y encontrar la más reciente
            incidents = []
            for key in keys:
                data = await self.redis.get_cache(key)
                if data:
                    incidents.append(data)

            if not incidents:
                return None

            # Ordenar por timestamp (más reciente primero)
            incidents.sort(
                key=lambda x: x.get('timestamp', ''),
                reverse=True
            )

            recent = incidents[0]

            # Verificar ventana temporal (2 horas por defecto)
            incident_time = datetime.fromisoformat(recent['timestamp'])
            time_diff = datetime.now() - incident_time

            if time_diff < timedelta(seconds=self.INCIDENT_TTL):
                logger.info("Found recent incident within time window",
                           ticket_id=recent['ticket_id'],
                           time_diff_seconds=time_diff.total_seconds())
                return recent['ticket_id']
            else:
                logger.debug("Recent incident found but outside time window",
                            ticket_id=recent['ticket_id'],
                            time_diff_seconds=time_diff.total_seconds())

            return None

        except Exception as e:
            logger.error("Error finding recent incident",
                        error=str(e))
            return None

    async def _scan_keys(self, pattern: str) -> List[str]:
        """
        Scan Redis keys by pattern (más eficiente que KEYS)

        Args:
            pattern: Patrón de búsqueda

        Returns:
            Lista de keys que coinciden
        """
        try:
            # Si el cliente Redis tiene el método scan, usarlo
            if hasattr(self.redis.redis, 'scan_iter'):
                keys = []
                async for key in self.redis.redis.scan_iter(match=pattern):
                    keys.append(key)
                return keys
            else:
                # Fallback a keys() si scan no está disponible
                if hasattr(self.redis.redis, 'keys'):
                    return await self.redis.redis.keys(pattern)
                return []
        except Exception as e:
            logger.error("Error scanning Redis keys", error=str(e), pattern=pattern)
            return []

    async def register_incident(self, message_data: Dict, ticket_id: str,
                               classification: Dict):
        """
        Registra nueva incidencia en Redis para tracking

        Args:
            message_data: Datos del mensaje original
            ticket_id: ID del ticket creado en Zoho
            classification: Resultado de la clasificación
        """
        try:
            # Convertir MessageData a dict si es necesario
            if hasattr(message_data, 'model_dump'):
                message_dict = message_data.model_dump()
            else:
                message_dict = message_data

            # Identificar contexto
            group_id = message_dict.get('group_id') or message_dict.get('from_user')
            user = message_dict.get('from_user') or message_dict.get('participant')

            incident_data = {
                'ticket_id': ticket_id,
                'original_message_id': message_dict.get('id'),
                'group_id': group_id,
                'user': user,
                'timestamp': datetime.now().isoformat(),
                'category': classification.get('categoria') or classification.get('category'),
                'priority': classification.get('prioridad') or classification.get('priority'),
                'message_text': message_dict.get('text', '')[:200],  # Primeros 200 chars
                'thread_messages': [message_dict.get('id')],
                'last_update': datetime.now().isoformat()
            }

            # Guardar en Redis con TTL
            key = f"{self.TICKET_PREFIX}{group_id}:{ticket_id}"
            success = await self.redis.set_cache(
                key,
                incident_data,
                ttl=self.INCIDENT_TTL
            )

            if success:
                logger.info("Incident registered in Redis",
                           ticket_id=ticket_id,
                           key=key,
                           ttl_seconds=self.INCIDENT_TTL)
            else:
                logger.error("Failed to register incident in Redis",
                            ticket_id=ticket_id,
                            key=key)

            return success

        except Exception as e:
            logger.error("Error registering incident",
                        error=str(e),
                        ticket_id=ticket_id)
            return False

    async def add_message_to_thread(self, ticket_id: str, message_id: str,
                                    message_text: str = "") -> bool:
        """
        Agrega mensaje al hilo de una incidencia existente

        Args:
            ticket_id: ID del ticket
            message_id: ID del nuevo mensaje
            message_text: Texto del mensaje (opcional, para logging)

        Returns:
            True si se agregó exitosamente, False si no
        """
        try:
            # Buscar la incidencia
            pattern = f"{self.TICKET_PREFIX}*:{ticket_id}"
            keys = await self._scan_keys(pattern)

            if not keys:
                logger.warning("Ticket not found for thread update",
                              ticket_id=ticket_id)
                return False

            key = keys[0]
            incident = await self.redis.get_cache(key)

            if not incident:
                logger.warning("Incident data not found",
                              ticket_id=ticket_id,
                              key=key)
                return False

            # Agregar mensaje al hilo
            if 'thread_messages' not in incident:
                incident['thread_messages'] = []

            incident['thread_messages'].append(message_id)
            incident['last_update'] = datetime.now().isoformat()

            if message_text:
                incident['last_message'] = message_text[:200]

            # Actualizar en Redis con TTL extendido
            success = await self.redis.set_cache(
                key,
                incident,
                ttl=self.INCIDENT_TTL
            )

            if success:
                logger.info("Message added to incident thread",
                           ticket_id=ticket_id,
                           message_id=message_id,
                           thread_size=len(incident['thread_messages']))
            else:
                logger.error("Failed to update incident thread",
                            ticket_id=ticket_id,
                            message_id=message_id)

            return success

        except Exception as e:
            logger.error("Error adding message to thread",
                        error=str(e),
                        ticket_id=ticket_id,
                        message_id=message_id)
            return False

    async def is_ticket_active(self, ticket_id: str) -> bool:
        """
        Verifica si un ticket sigue activo en Redis

        Args:
            ticket_id: ID del ticket

        Returns:
            True si está activo, False si no
        """
        try:
            pattern = f"{self.TICKET_PREFIX}*:{ticket_id}"
            keys = await self._scan_keys(pattern)
            is_active = len(keys) > 0

            logger.debug("Ticket active check",
                        ticket_id=ticket_id,
                        is_active=is_active)

            return is_active

        except Exception as e:
            logger.error("Error checking ticket active status",
                        error=str(e),
                        ticket_id=ticket_id)
            return False

    async def get_thread_summary(self, ticket_id: str) -> Optional[Dict]:
        """
        Obtiene resumen del hilo de conversación

        Args:
            ticket_id: ID del ticket

        Returns:
            Dict con datos del hilo o None si no existe
        """
        try:
            pattern = f"{self.TICKET_PREFIX}*:{ticket_id}"
            keys = await self._scan_keys(pattern)

            if not keys:
                return None

            incident = await self.redis.get_cache(keys[0])

            if incident:
                logger.info("Thread summary retrieved",
                           ticket_id=ticket_id,
                           message_count=len(incident.get('thread_messages', [])))

            return incident

        except Exception as e:
            logger.error("Error getting thread summary",
                        error=str(e),
                        ticket_id=ticket_id)
            return None

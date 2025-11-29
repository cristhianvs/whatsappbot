"""
Script Principal de Testing
Clasifica 50 mensajes del archivo _chat.txt usando Claude y OpenAI en paralelo
"""
import os
import sys
import json
import csv
import random
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple
from dotenv import load_dotenv
import concurrent.futures

# Cargar variables de entorno
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

# Importar clasificadores
from claude_classifier import ClaudeClassifier
from openai_classifier import OpenAIClassifier
from voting_system import VotingSystem

class ChatParser:
    """Parser para extraer mensajes del archivo _chat.txt de WhatsApp"""

    # Patrón de mensaje de WhatsApp
    # Formato: [DD/MM/YY, HH:MM:SS a.m./p.m.] Usuario: Mensaje
    MESSAGE_PATTERN = r'\[(\d{1,2}/\d{1,2}/\d{2}),\s*(\d{1,2}:\d{2}:\d{2}\s*(?:a\.|p\.)\s*m\.)\]\s+([^:]+):\s+(.+)'

    @staticmethod
    def parse_chat_file(file_path: str) -> List[Dict]:
        """
        Parsea el archivo de chat y extrae mensajes de usuarios

        Args:
            file_path: Ruta al archivo _chat.txt

        Returns:
            Lista de mensajes con metadata
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        mensajes = []
        lines = content.split('\n')
        current_message = None

        for line in lines:
            # Intentar match con patrón de mensaje
            match = re.match(ChatParser.MESSAGE_PATTERN, line)

            if match:
                # Si hay un mensaje previo, guardarlo
                if current_message:
                    mensajes.append(current_message)

                # Iniciar nuevo mensaje
                fecha, hora, usuario, texto = match.groups()
                current_message = {
                    'fecha': fecha,
                    'hora': hora,
                    'usuario': usuario.strip(),
                    'texto': texto.strip(),
                    'texto_completo': texto.strip()
                }
            elif current_message:
                # Línea continuación del mensaje anterior
                current_message['texto_completo'] += '\n' + line

        # Agregar último mensaje
        if current_message:
            mensajes.append(current_message)

        return mensajes

    @staticmethod
    def filtrar_mensajes_validos(mensajes: List[Dict]) -> List[Dict]:
        """
        Filtra mensajes válidos (no son del sistema, tienen texto, etc.)

        Args:
            mensajes: Lista de todos los mensajes

        Returns:
            Lista filtrada de mensajes válidos para clasificar
        """
        mensajes_validos = []

        for msg in mensajes:
            texto = msg['texto_completo'].strip()
            usuario = msg['usuario']

            # Filtrar mensajes del sistema
            if any(x in texto.lower() for x in ['añadió', 'quitó', 'cambió', 'creó este grupo']):
                continue

            # Filtrar menciones a archivos sin texto
            if texto.startswith('<') and texto.endswith('>'):
                continue

            # Filtrar mensajes muy cortos (probablemente no informativos)
            if len(texto) < 3:
                continue

            # Filtrar solo emojis
            if all(c in '👍✅❌🙏💪🎉😊' for c in texto.replace(' ', '')):
                continue

            mensajes_validos.append(msg)

        return mensajes_validos

    @staticmethod
    def seleccionar_muestra_estratificada(mensajes: List[Dict], n: int = 50) -> List[Dict]:
        """
        Selecciona muestra estratificada de mensajes

        Estrategia:
        - 60% mensajes con keywords de incidencia
        - 40% mensajes random (para capturar no-incidencias)

        Args:
            mensajes: Lista de todos los mensajes
            n: Número de mensajes a seleccionar

        Returns:
            Muestra seleccionada
        """
        # Keywords que sugieren incidencias
        keywords_incidencia = [
            'error', 'no funciona', 'no deja', 'no aparece', 'problema',
            'falla', 'urgente', 'ayuda', 'apoyo', 'no se puede'
        ]

        # Separar mensajes con/sin keywords
        con_keywords = []
        sin_keywords = []

        for msg in mensajes:
            texto_lower = msg['texto_completo'].lower()
            tiene_keyword = any(kw in texto_lower for kw in keywords_incidencia)

            if tiene_keyword:
                con_keywords.append(msg)
            else:
                sin_keywords.append(msg)

        # Calcular cantidad por grupo
        n_con_keywords = int(n * 0.6)  # 60%
        n_sin_keywords = n - n_con_keywords  # 40%

        # Seleccionar random de cada grupo
        muestra_con_kw = random.sample(con_keywords, min(n_con_keywords, len(con_keywords)))
        muestra_sin_kw = random.sample(sin_keywords, min(n_sin_keywords, len(sin_keywords)))

        # Combinar y mezclar
        muestra = muestra_con_kw + muestra_sin_kw
        random.shuffle(muestra)

        return muestra[:n]


class TestRunner:
    """Ejecuta las pruebas de clasificación"""

    def __init__(self):
        self.claude = ClaudeClassifier()
        self.openai = OpenAIClassifier()
        self.voting = VotingSystem()

    def clasificar_mensaje(self, mensaje: Dict) -> Dict:
        """
        Clasifica un mensaje con ambos LLMs en paralelo

        Args:
            mensaje: Dict con texto y metadata del mensaje

        Returns:
            Resultado de clasificación consensuada
        """
        texto = mensaje['texto_completo']

        print(f"\n{'='*80}")
        print(f"Clasificando: {texto[:100]}...")

        # Clasificar en paralelo con ThreadPoolExecutor
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            future_claude = executor.submit(self.claude.classify, texto, mensaje)
            future_openai = executor.submit(self.openai.classify, texto, mensaje)

            resultado_claude = future_claude.result()
            resultado_openai = future_openai.result()

        # Aplicar voting system
        resultado_final = self.voting.consensus(resultado_claude, resultado_openai)

        # Agregar mensaje original al resultado
        resultado_final['mensaje_original'] = {
            'texto': texto,
            'usuario': mensaje['usuario'],
            'fecha': mensaje['fecha'],
            'hora': mensaje['hora']
        }

        # Agregar resultados individuales
        resultado_final['claude_result'] = resultado_claude
        resultado_final['openai_result'] = resultado_openai

        # Mostrar resultado
        print(f"Claude: {resultado_claude.get('es_incidencia')} (conf: {resultado_claude.get('confianza')})")
        print(f"OpenAI: {resultado_openai.get('es_incidencia')} (conf: {resultado_openai.get('confianza')})")
        print(f"Consenso: {resultado_final.get('es_incidencia')} (conf: {resultado_final.get('confianza')})")
        print(f"Tipo: {resultado_final['consenso']['tipo']}")

        return resultado_final

    def run_test(self, chat_file: str, n_mensajes: int = 50):
        """
        Ejecuta el test completo

        Args:
            chat_file: Ruta al archivo _chat.txt
            n_mensajes: Número de mensajes a clasificar
        """
        print(f"\n🚀 Iniciando Test de Clasificación")
        print(f"{'='*80}\n")

        # 1. Parsear archivo de chat
        print("📖 Parseando archivo de chat...")
        mensajes = ChatParser.parse_chat_file(chat_file)
        print(f"   Total mensajes encontrados: {len(mensajes)}")

        # 2. Filtrar mensajes válidos
        print("\n🔍 Filtrando mensajes válidos...")
        mensajes_validos = ChatParser.filtrar_mensajes_validos(mensajes)
        print(f"   Mensajes válidos: {len(mensajes_validos)}")

        # 3. Seleccionar muestra estratificada
        print(f"\n🎲 Seleccionando muestra de {n_mensajes} mensajes...")
        muestra = ChatParser.seleccionar_muestra_estratificada(mensajes_validos, n_mensajes)
        print(f"   Muestra seleccionada: {len(muestra)} mensajes")

        # 4. Clasificar cada mensaje
        print(f"\n🤖 Clasificando mensajes con Claude + OpenAI...")
        resultados = []

        for i, mensaje in enumerate(muestra, 1):
            print(f"\n[{i}/{len(muestra)}]")
            try:
                resultado = self.clasificar_mensaje(mensaje)
                resultados.append(resultado)
            except Exception as e:
                print(f"❌ Error clasificando mensaje: {e}")
                # Agregar resultado de error
                resultados.append({
                    'mensaje_original': mensaje,
                    'es_incidencia': None,
                    'confianza': 0.0,
                    'error': str(e)
                })

        # 5. Generar reportes
        print(f"\n📊 Generando reportes...")
        self.generar_reportes(resultados)

        print(f"\n✅ Test completado!")
        print(f"   Total clasificaciones: {len(resultados)}")
        print(f"   Reportes generados en: ./results/")

    def generar_reportes(self, resultados: List[Dict]):
        """Genera reportes CSV y JSON con los resultados"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        results_dir = Path(__file__).parent / 'results'
        results_dir.mkdir(exist_ok=True)

        # 1. Reporte JSON completo
        json_file = results_dir / f'test_results_{timestamp}.json'
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(resultados, f, ensure_ascii=False, indent=2)
        print(f"   ✅ JSON: {json_file}")

        # 2. Reporte CSV para validación manual
        csv_file = results_dir / f'validation_{timestamp}.csv'
        with open(csv_file, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)

            # Header
            writer.writerow([
                'Num',
                'Usuario',
                'Mensaje',
                'Claude_Incidencia',
                'Claude_Confianza',
                'OpenAI_Incidencia',
                'OpenAI_Confianza',
                'Consenso_Incidencia',
                'Consenso_Confianza',
                'Tipo_Consenso',
                'Categoria',
                'Prioridad',
                'Validacion_Manual',
                'Notas'
            ])

            # Rows
            for i, resultado in enumerate(resultados, 1):
                msg_orig = resultado.get('mensaje_original', {})
                claude_res = resultado.get('claude_result', {})
                openai_res = resultado.get('openai_result', {})

                writer.writerow([
                    i,
                    msg_orig.get('usuario', ''),
                    msg_orig.get('texto', '')[:200],  # Truncar mensaje largo
                    '✅ Sí' if claude_res.get('es_incidencia') else '❌ No',
                    claude_res.get('confianza', 0.0),
                    '✅ Sí' if openai_res.get('es_incidencia') else '❌ No',
                    openai_res.get('confianza', 0.0),
                    '✅ Sí' if resultado.get('es_incidencia') else '❌ No',
                    resultado.get('confianza', 0.0),
                    resultado.get('consenso', {}).get('tipo', ''),
                    resultado.get('categoria', ''),
                    resultado.get('prioridad', ''),
                    '',  # Para que el usuario llene manualmente
                    ''   # Para notas
                ])

        print(f"   ✅ CSV: {csv_file}")

        # 3. Reporte de estadísticas
        stats_file = results_dir / f'stats_{timestamp}.txt'
        self._generar_stats(resultados, stats_file)
        print(f"   ✅ Stats: {stats_file}")

    def _generar_stats(self, resultados: List[Dict], output_file: Path):
        """Genera reporte de estadísticas"""
        total = len(resultados)

        # Contar por consenso
        ambos_si = sum(1 for r in resultados if r.get('consenso', {}).get('tipo') == 'ambos_si')
        ambos_no = sum(1 for r in resultados if r.get('consenso', {}).get('tipo') == 'ambos_no')
        discrepancia = sum(1 for r in resultados if r.get('consenso', {}).get('tipo') == 'discrepancia')
        errores = sum(1 for r in resultados if r.get('consenso', {}).get('tipo', '').startswith('error'))

        # Tiempos y costos
        tiempos_claude = [r.get('claude_result', {}).get('_metadata', {}).get('tiempo_ms', 0) for r in resultados]
        tiempos_openai = [r.get('openai_result', {}).get('_metadata', {}).get('tiempo_ms', 0) for r in resultados]

        costos_claude = [r.get('claude_result', {}).get('_metadata', {}).get('costo_estimado_usd', 0) for r in resultados]
        costos_openai = [r.get('openai_result', {}).get('_metadata', {}).get('costo_estimado_usd', 0) for r in resultados]

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("="*80 + "\n")
            f.write("ESTADÍSTICAS DEL TEST DE CLASIFICACIÓN\n")
            f.write("="*80 + "\n\n")

            f.write(f"Total de mensajes clasificados: {total}\n\n")

            f.write("CONSENSO:\n")
            f.write(f"  Ambos Sí (incidencia): {ambos_si} ({ambos_si/total*100:.1f}%)\n")
            f.write(f"  Ambos No: {ambos_no} ({ambos_no/total*100:.1f}%)\n")
            f.write(f"  Discrepancia: {discrepancia} ({discrepancia/total*100:.1f}%)\n")
            f.write(f"  Errores: {errores} ({errores/total*100:.1f}%)\n\n")

            f.write("TIEMPOS PROMEDIO:\n")
            f.write(f"  Claude: {sum(tiempos_claude)/len(tiempos_claude):.0f} ms\n")
            f.write(f"  OpenAI: {sum(tiempos_openai)/len(tiempos_openai):.0f} ms\n\n")

            f.write("COSTOS ESTIMADOS:\n")
            f.write(f"  Claude: ${sum(costos_claude):.4f}\n")
            f.write(f"  OpenAI: ${sum(costos_openai):.4f}\n")
            f.write(f"  Total: ${sum(costos_claude) + sum(costos_openai):.4f}\n")


if __name__ == '__main__':
    # Ruta al archivo de chat
    CHAT_FILE = r"C:\Users\Cristhian\Documents\Programacion\whatsappbot\whatsappbot\tests\Mensajes Grupo Whatsapp\WhatsApp Chat - Migración SAP S_4 Hana\_chat.txt"

    # Verificar que existe
    if not os.path.exists(CHAT_FILE):
        print(f"❌ Error: Archivo no encontrado: {CHAT_FILE}")
        sys.exit(1)

    # Ejecutar test
    runner = TestRunner()
    runner.run_test(CHAT_FILE, n_mensajes=50)

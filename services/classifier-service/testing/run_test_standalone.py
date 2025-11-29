#!/usr/bin/env -S uv run --quiet --script
# /// script
# dependencies = [
#   "anthropic",
#   "openai",
#   "python-dotenv"
# ]
# ///
"""
Script Principal de Testing - Standalone con UV
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
import time

# Cargar variables de entorno desde el directorio padre
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

# Imports de APIs
import anthropic
from openai import OpenAI

# ============================================================================
# CLAUDE CLASSIFIER
# ============================================================================

class ClaudeClassifier:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv('ANTHROPIC_API_KEY')
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY no encontrada")

        self.client = anthropic.Anthropic(api_key=self.api_key)
        self.model = "claude-sonnet-4-20250514"

        # Cargar prompt
        prompts_dir = Path(__file__).parent / "prompts"
        prompt_file = prompts_dir / "incident_classifier.txt"

        with open(prompt_file, 'r', encoding='utf-8') as f:
            self.system_prompt = f.read()

    def classify(self, mensaje: str, metadata: Dict = None) -> Dict:
        start_time = time.time()

        try:
            user_message = f"Mensaje a clasificar:\n\n{mensaje}"

            response = self.client.messages.create(
                model=self.model,
                max_tokens=1000,
                temperature=0.1,
                system=self.system_prompt,
                messages=[{"role": "user", "content": user_message}]
            )

            response_text = response.content[0].text.strip()

            # Limpiar JSON si viene envuelto
            if response_text.startswith('```json'):
                response_text = response_text[7:]
            if response_text.endswith('```'):
                response_text = response_text[:-3]
            response_text = response_text.strip()

            result = json.loads(response_text)
            elapsed_time = (time.time() - start_time) * 1000

            result['_metadata'] = {
                'modelo': self.model,
                'tiempo_ms': round(elapsed_time, 2),
                'tokens_input': response.usage.input_tokens,
                'tokens_output': response.usage.output_tokens,
                'costo_estimado_usd': (response.usage.input_tokens / 1_000_000 * 3.00) +
                                     (response.usage.output_tokens / 1_000_000 * 15.00)
            }

            return result

        except Exception as e:
            elapsed_time = (time.time() - start_time) * 1000
            return {
                'es_incidencia': None,
                'confianza': 0.0,
                'razonamiento': f'Error: {str(e)}',
                'categoria': None,
                'prioridad': None,
                'metadata': {},
                '_metadata': {'modelo': self.model, 'tiempo_ms': round(elapsed_time, 2), 'error': str(e)}
            }

# ============================================================================
# OPENAI CLASSIFIER
# ============================================================================

class OpenAIClassifier:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY no encontrada")

        self.client = OpenAI(api_key=self.api_key)
        self.model = "gpt-4o-mini"

        prompts_dir = Path(__file__).parent / "prompts"
        prompt_file = prompts_dir / "incident_classifier.txt"

        with open(prompt_file, 'r', encoding='utf-8') as f:
            self.system_prompt = f.read()

    def classify(self, mensaje: str, metadata: Dict = None) -> Dict:
        start_time = time.time()

        try:
            user_message = f"Mensaje a clasificar:\n\n{mensaje}"

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.1,
                max_tokens=1000,
                response_format={"type": "json_object"}
            )

            response_text = response.choices[0].message.content
            result = json.loads(response_text)
            elapsed_time = (time.time() - start_time) * 1000

            result['_metadata'] = {
                'modelo': self.model,
                'tiempo_ms': round(elapsed_time, 2),
                'tokens_input': response.usage.prompt_tokens,
                'tokens_output': response.usage.completion_tokens,
                'costo_estimado_usd': (response.usage.prompt_tokens / 1_000_000 * 0.150) +
                                     (response.usage.completion_tokens / 1_000_000 * 0.600)
            }

            return result

        except Exception as e:
            elapsed_time = (time.time() - start_time) * 1000
            return {
                'es_incidencia': None,
                'confianza': 0.0,
                'razonamiento': f'Error: {str(e)}',
                'categoria': None,
                'prioridad': None,
                'metadata': {},
                '_metadata': {'modelo': self.model, 'tiempo_ms': round(elapsed_time, 2), 'error': str(e)}
            }

# ============================================================================
# VOTING SYSTEM
# ============================================================================

class VotingSystem:
    @staticmethod
    def consensus(claude_result: Dict, openai_result: Dict) -> Dict:
        claude_es_inc = claude_result.get('es_incidencia')
        openai_es_inc = openai_result.get('es_incidencia')

        claude_conf = claude_result.get('confianza', 0.0)
        openai_conf = openai_result.get('confianza', 0.0)

        # Ambos SÍ
        if claude_es_inc is True and openai_es_inc is True:
            confianza_final = min((claude_conf + openai_conf) / 2 * 1.1, 1.0)

            if claude_conf >= openai_conf:
                categoria, prioridad, metadata = claude_result.get('categoria'), claude_result.get('prioridad'), claude_result.get('metadata', {})
            else:
                categoria, prioridad, metadata = openai_result.get('categoria'), openai_result.get('prioridad'), openai_result.get('metadata', {})

            return {
                'es_incidencia': True,
                'confianza': round(confianza_final, 3),
                'categoria': categoria,
                'prioridad': prioridad,
                'metadata': metadata,
                'consenso': {'tipo': 'ambos_si', 'requiere_revision': False}
            }

        # Ambos NO
        if claude_es_inc is False and openai_es_inc is False:
            return {
                'es_incidencia': False,
                'confianza': round(max(claude_conf, openai_conf), 3),
                'categoria': None,
                'prioridad': None,
                'metadata': {},
                'consenso': {'tipo': 'ambos_no', 'requiere_revision': False}
            }

        # Discrepancia
        if claude_es_inc is not None and openai_es_inc is not None and claude_es_inc != openai_es_inc:
            if claude_conf > openai_conf:
                resultado = claude_result
                modelo = 'claude'
            else:
                resultado = openai_result
                modelo = 'openai'

            return {
                'es_incidencia': resultado.get('es_incidencia'),
                'confianza': round(resultado.get('confianza', 0.0) * 0.85, 3),
                'categoria': resultado.get('categoria'),
                'prioridad': resultado.get('prioridad'),
                'metadata': resultado.get('metadata', {}),
                'consenso': {'tipo': 'discrepancia', 'modelo_primario': modelo, 'requiere_revision': True}
            }

        # Error
        return {
            'es_incidencia': None,
            'confianza': 0.0,
            'categoria': None,
            'prioridad': None,
            'metadata': {},
            'consenso': {'tipo': 'error', 'requiere_revision': True}
        }

# ============================================================================
# CHAT PARSER
# ============================================================================

class ChatParser:
    MESSAGE_PATTERN = r'\[(\d{1,2}/\d{1,2}/\d{2}),\s*(\d{1,2}:\d{2}:\d{2}\s*(?:a\.|p\.)\s*m\.)\]\s+([^:]+):\s+(.+)'

    @staticmethod
    def parse_chat_file(file_path: str) -> List[Dict]:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        mensajes = []
        lines = content.split('\n')
        current_message = None

        for line in lines:
            match = re.match(ChatParser.MESSAGE_PATTERN, line)

            if match:
                if current_message:
                    mensajes.append(current_message)

                fecha, hora, usuario, texto = match.groups()
                current_message = {
                    'fecha': fecha,
                    'hora': hora,
                    'usuario': usuario.strip(),
                    'texto': texto.strip(),
                    'texto_completo': texto.strip()
                }
            elif current_message:
                current_message['texto_completo'] += '\n' + line

        if current_message:
            mensajes.append(current_message)

        return mensajes

    @staticmethod
    def filtrar_mensajes_validos(mensajes: List[Dict]) -> List[Dict]:
        mensajes_validos = []

        for msg in mensajes:
            texto = msg['texto_completo'].strip()

            if any(x in texto.lower() for x in ['añadió', 'quitó', 'cambió', 'creó este grupo']):
                continue

            if texto.startswith('<') and texto.endswith('>'):
                continue

            if len(texto) < 3:
                continue

            mensajes_validos.append(msg)

        return mensajes_validos

    @staticmethod
    def seleccionar_muestra_estratificada(mensajes: List[Dict], n: int = 50) -> List[Dict]:
        keywords_incidencia = [
            'error', 'no funciona', 'no deja', 'no aparece', 'problema',
            'falla', 'urgente', 'ayuda', 'apoyo', 'no se puede'
        ]

        con_keywords = []
        sin_keywords = []

        for msg in mensajes:
            texto_lower = msg['texto_completo'].lower()
            tiene_keyword = any(kw in texto_lower for kw in keywords_incidencia)

            if tiene_keyword:
                con_keywords.append(msg)
            else:
                sin_keywords.append(msg)

        n_con_keywords = int(n * 0.6)
        n_sin_keywords = n - n_con_keywords

        muestra_con_kw = random.sample(con_keywords, min(n_con_keywords, len(con_keywords)))
        muestra_sin_kw = random.sample(sin_keywords, min(n_sin_keywords, len(sin_keywords)))

        muestra = muestra_con_kw + muestra_sin_kw
        random.shuffle(muestra)

        return muestra[:n]

# ============================================================================
# TEST RUNNER
# ============================================================================

class TestRunner:
    def __init__(self):
        self.claude = ClaudeClassifier()
        self.openai = OpenAIClassifier()
        self.voting = VotingSystem()

    def clasificar_mensaje(self, mensaje: Dict) -> Dict:
        texto = mensaje['texto_completo']

        print(f"\n{'='*80}")
        print(f"Clasificando: {texto[:100]}...")

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            future_claude = executor.submit(self.claude.classify, texto, mensaje)
            future_openai = executor.submit(self.openai.classify, texto, mensaje)

            resultado_claude = future_claude.result()
            resultado_openai = future_openai.result()

        resultado_final = self.voting.consensus(resultado_claude, resultado_openai)

        resultado_final['mensaje_original'] = {
            'texto': texto,
            'usuario': mensaje['usuario'],
            'fecha': mensaje['fecha'],
            'hora': mensaje['hora']
        }

        resultado_final['claude_result'] = resultado_claude
        resultado_final['openai_result'] = resultado_openai

        print(f"Claude: {resultado_claude.get('es_incidencia')} (conf: {resultado_claude.get('confianza')})")
        print(f"OpenAI: {resultado_openai.get('es_incidencia')} (conf: {resultado_openai.get('confianza')})")
        print(f"Consenso: {resultado_final.get('es_incidencia')} (conf: {resultado_final.get('confianza')})")

        return resultado_final

    def run_test(self, chat_file: str, n_mensajes: int = 50):
        print(f"\n>> Iniciando Test de Clasificacion")
        print(f"{'='*80}\n")

        print(">> Parseando archivo de chat...")
        mensajes = ChatParser.parse_chat_file(chat_file)
        print(f"   Total mensajes encontrados: {len(mensajes)}")

        print("\n>> Filtrando mensajes validos...")
        mensajes_validos = ChatParser.filtrar_mensajes_validos(mensajes)
        print(f"   Mensajes validos: {len(mensajes_validos)}")

        print(f"\n>> Seleccionando muestra de {n_mensajes} mensajes...")
        muestra = ChatParser.seleccionar_muestra_estratificada(mensajes_validos, n_mensajes)
        print(f"   Muestra seleccionada: {len(muestra)} mensajes")

        print(f"\n>> Clasificando mensajes con Claude + OpenAI...")
        resultados = []

        for i, mensaje in enumerate(muestra, 1):
            print(f"\n[{i}/{len(muestra)}]")
            try:
                resultado = self.clasificar_mensaje(mensaje)
                resultados.append(resultado)
            except Exception as e:
                print(f"ERROR: {e}")
                resultados.append({
                    'mensaje_original': mensaje,
                    'es_incidencia': None,
                    'confianza': 0.0,
                    'error': str(e)
                })

        print(f"\n>> Generando reportes...")
        self.generar_reportes(resultados)

        print(f"\n>> Test completado!")
        print(f"   Total clasificaciones: {len(resultados)}")

    def generar_reportes(self, resultados: List[Dict]):
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        results_dir = Path(__file__).parent / 'results'
        results_dir.mkdir(exist_ok=True)

        # JSON completo
        json_file = results_dir / f'test_results_{timestamp}.json'
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(resultados, f, ensure_ascii=False, indent=2)
        print(f"   OK JSON: {json_file}")

        # CSV para validación
        csv_file = results_dir / f'validation_{timestamp}.csv'
        with open(csv_file, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)

            writer.writerow([
                'Num', 'Usuario', 'Mensaje', 'Claude_Incidencia', 'Claude_Confianza',
                'OpenAI_Incidencia', 'OpenAI_Confianza', 'Consenso_Incidencia',
                'Consenso_Confianza', 'Tipo_Consenso', 'Categoria', 'Prioridad',
                'Validacion_Manual', 'Notas'
            ])

            for i, resultado in enumerate(resultados, 1):
                msg_orig = resultado.get('mensaje_original', {})
                claude_res = resultado.get('claude_result', {})
                openai_res = resultado.get('openai_result', {})

                writer.writerow([
                    i,
                    msg_orig.get('usuario', ''),
                    msg_orig.get('texto', '')[:200],
                    'Si' if claude_res.get('es_incidencia') else 'No',
                    claude_res.get('confianza', 0.0),
                    'Si' if openai_res.get('es_incidencia') else 'No',
                    openai_res.get('confianza', 0.0),
                    'Si' if resultado.get('es_incidencia') else 'No',
                    resultado.get('confianza', 0.0),
                    resultado.get('consenso', {}).get('tipo', ''),
                    resultado.get('categoria', ''),
                    resultado.get('prioridad', ''),
                    '',
                    ''
                ])

        print(f"   OK CSV: {csv_file}")

        # Stats
        self._generar_stats(resultados, results_dir / f'stats_{timestamp}.txt')

    def _generar_stats(self, resultados: List[Dict], output_file: Path):
        total = len(resultados)
        ambos_si = sum(1 for r in resultados if r.get('consenso', {}).get('tipo') == 'ambos_si')
        ambos_no = sum(1 for r in resultados if r.get('consenso', {}).get('tipo') == 'ambos_no')
        discrepancia = sum(1 for r in resultados if r.get('consenso', {}).get('tipo') == 'discrepancia')

        tiempos_claude = [r.get('claude_result', {}).get('_metadata', {}).get('tiempo_ms', 0) for r in resultados if r.get('claude_result')]
        tiempos_openai = [r.get('openai_result', {}).get('_metadata', {}).get('tiempo_ms', 0) for r in resultados if r.get('openai_result')]

        costos_claude = [r.get('claude_result', {}).get('_metadata', {}).get('costo_estimado_usd', 0) for r in resultados if r.get('claude_result')]
        costos_openai = [r.get('openai_result', {}).get('_metadata', {}).get('costo_estimado_usd', 0) for r in resultados if r.get('openai_result')]

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("="*80 + "\n")
            f.write("ESTADÍSTICAS DEL TEST DE CLASIFICACIÓN\n")
            f.write("="*80 + "\n\n")
            f.write(f"Total de mensajes clasificados: {total}\n\n")
            f.write("CONSENSO:\n")
            f.write(f"  Ambos Sí (incidencia): {ambos_si} ({ambos_si/total*100:.1f}%)\n")
            f.write(f"  Ambos No: {ambos_no} ({ambos_no/total*100:.1f}%)\n")
            f.write(f"  Discrepancia: {discrepancia} ({discrepancia/total*100:.1f}%)\n\n")
            f.write("TIEMPOS PROMEDIO:\n")
            f.write(f"  Claude: {sum(tiempos_claude)/len(tiempos_claude):.0f} ms\n" if tiempos_claude else "  Claude: N/A\n")
            f.write(f"  OpenAI: {sum(tiempos_openai)/len(tiempos_openai):.0f} ms\n" if tiempos_openai else "  OpenAI: N/A\n")
            f.write("\nCOSTOS ESTIMADOS:\n")
            f.write(f"  Claude: ${sum(costos_claude):.4f}\n" if costos_claude else "  Claude: $0.0000\n")
            f.write(f"  OpenAI: ${sum(costos_openai):.4f}\n" if costos_openai else "  OpenAI: $0.0000\n")
            f.write(f"  Total: ${sum(costos_claude) + sum(costos_openai):.4f}\n" if (costos_claude or costos_openai) else "  Total: $0.0000\n")

        print(f"   OK Stats: {output_file}")

if __name__ == '__main__':
    # Buscar el archivo dinamicamente para evitar problemas de encoding
    import glob
    base_path = Path(__file__).parent.parent.parent.parent / "tests" / "Mensajes Grupo Whatsapp"

    # Buscar el archivo _chat.txt en cualquier subdirectorio
    chat_files = list(base_path.glob("**/_chat.txt"))

    if not chat_files:
        print(f"ERROR: Archivo _chat.txt no encontrado en: {base_path}")
        sys.exit(1)

    CHAT_FILE = str(chat_files[0])
    print(f">> Archivo encontrado\n")

    runner = TestRunner()
    runner.run_test(CHAT_FILE, n_mensajes=50)

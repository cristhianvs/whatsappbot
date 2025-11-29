# Sistema de Testing - Clasificador de Incidencias

Sistema de testing para validar la clasificación de mensajes de WhatsApp como incidencias técnicas usando Claude Sonnet 4.5 y GPT-4o-mini en paralelo.

## Estructura de Archivos

```
testing/
├── claude_classifier.py      # Clasificador con Claude Sonnet 4.5
├── openai_classifier.py      # Clasificador con GPT-4o-mini
├── voting_system.py          # Sistema de consenso entre modelos
├── run_test.py               # Script principal de testing
├── prompts/
│   └── incident_classifier.txt  # Prompt estructurado
├── results/                  # Reportes generados
│   ├── test_results_*.json  # Resultados completos
│   ├── validation_*.csv     # Para validación manual
│   └── stats_*.txt          # Estadísticas
└── README.md
```

## Requisitos

### 1. Dependencias Python

```bash
pip install anthropic openai python-dotenv
```

O con UV (recomendado):

```bash
cd services/classifier-service
uv add anthropic openai python-dotenv
```

### 2. Variables de Entorno

Asegúrate de que el archivo `.env` en `services/classifier-service/` contenga:

```bash
ANTHROPIC_API_KEY=sk-ant-api03-...
OPENAI_API_KEY=sk-proj-...
```

## Uso

### Ejecutar Test con 50 Mensajes

```bash
cd services/classifier-service/testing
python run_test.py
```

### Personalizar Número de Mensajes

Edita el archivo `run_test.py` línea final:

```python
runner.run_test(CHAT_FILE, n_mensajes=100)  # Cambiar a 100 mensajes
```

## Flujo del Test

1. **Parsear archivo `_chat.txt`**: Lee y parsea mensajes del grupo de WhatsApp
2. **Filtrar mensajes válidos**: Elimina mensajes del sistema, muy cortos, etc.
3. **Seleccionar muestra estratificada**:
   - 60% mensajes con keywords de incidencia
   - 40% mensajes random (para capturar no-incidencias)
4. **Clasificar con ambos LLMs en paralelo**:
   - Claude Sonnet 4.5
   - GPT-4o-mini
5. **Aplicar sistema de voting/consensus**:
   - Ambos Sí → Alta confianza
   - Ambos No → Alta confianza
   - Discrepancia → Usar el de mayor confianza con penalización
6. **Generar reportes**:
   - JSON completo con todos los detalles
   - CSV para validación manual
   - TXT con estadísticas

## Reportes Generados

### 1. `test_results_YYYYMMDD_HHMMSS.json`

Contiene todos los resultados completos:
- Mensaje original
- Clasificación de Claude (completa)
- Clasificación de OpenAI (completa)
- Resultado de consenso
- Metadata de comparación

### 2. `validation_YYYYMMDD_HHMMSS.csv`

CSV para que valides manualmente:

| Num | Usuario | Mensaje | Claude_Incidencia | ... | Validacion_Manual | Notas |
|-----|---------|---------|-------------------|-----|-------------------|-------|
| 1 | Lluvia | Tienda 907... | ✅ Sí | ... | **[LLENAR]** | |

**Instrucciones:**
1. Abre el CSV en Excel/Google Sheets
2. En columna "Validacion_Manual" escribe: `CORRECTO`, `INCORRECTO` o `DUDOSO`
3. En "Notas" agrega comentarios si es necesario

### 3. `stats_YYYYMMDD_HHMMSS.txt`

Estadísticas del test:
- Total de clasificaciones
- Distribución de consenso (ambos sí, ambos no, discrepancia)
- Tiempos promedio por modelo
- Costos estimados

## Ejemplo de Salida

```
🚀 Iniciando Test de Clasificación
================================================================================

📖 Parseando archivo de chat...
   Total mensajes encontrados: 3052

🔍 Filtrando mensajes válidos...
   Mensajes válidos: 2440

🎲 Seleccionando muestra de 50 mensajes...
   Muestra seleccionada: 50 mensajes

🤖 Clasificando mensajes con Claude + OpenAI...

[1/50]
================================================================================
Clasificando: Tienda 907 no deja cobrar marca error...
Claude: True (conf: 0.96)
OpenAI: True (conf: 0.94)
Consenso: True (conf: 0.95)
Tipo: ambos_si

[2/50]
================================================================================
Clasificando: Ok gracias...
Claude: False (conf: 0.99)
OpenAI: False (conf: 0.98)
Consenso: False (conf: 0.99)
Tipo: ambos_no

...

📊 Generando reportes...
   ✅ JSON: ./results/test_results_20251115_143000.json
   ✅ CSV: ./results/validation_20251115_143000.csv
   ✅ Stats: ./results/stats_20251115_143000.txt

✅ Test completado!
   Total clasificaciones: 50
   Reportes generados en: ./results/
```

## Interpretación de Resultados

### Tipo de Consenso

| Tipo | Significado | Confianza |
|------|-------------|-----------|
| `ambos_si` | Ambos modelos dicen que SÍ es incidencia | Alta (promedio + 10% bonus) |
| `ambos_no` | Ambos modelos dicen que NO es incidencia | Alta (máxima de ambos) |
| `discrepancia` | Un modelo dice SÍ y otro NO | Media (penalización 15%) |
| `error_parcial` | Un modelo falló | Baja (penalización 25%) |
| `error_ambos` | Ambos modelos fallaron | Nula (0.0) |

### Umbrales de Confianza

| Confianza | Acción Sugerida |
|-----------|-----------------|
| > 0.90 | Auto-crear ticket en Zoho |
| 0.60 - 0.90 | Pedir confirmación al usuario |
| < 0.60 | Solo registrar en log |

## Validación Manual

Después de ejecutar el test:

1. Abre el CSV generado
2. Revisa las clasificaciones
3. Marca como CORRECTO/INCORRECTO
4. Calcula accuracy:
   - `Accuracy = CORRECTOS / TOTAL`
5. Si accuracy < 90%, ajusta el prompt y repite

## Ajustar el Prompt

Si los resultados no son satisfactorios, edita:

```
prompts/incident_classifier.txt
```

Y modifica:
- Ejemplos en el prompt
- Criterios de clasificación
- Palabras clave
- Categorías

Luego ejecuta el test nuevamente.

## Costos Estimados

### Por Mensaje (aprox):
- Claude Sonnet 4.5: ~$0.003
- GPT-4o-mini: ~$0.0005
- **Total por mensaje: ~$0.0035**

### Test Completo (50 mensajes):
- **Costo estimado: ~$0.18**

### Producción (68 incidencias/día):
- **Costo diario: ~$0.24**
- **Costo mensual: ~$7.20**

## Troubleshooting

### Error: "ANTHROPIC_API_KEY no encontrada"

```bash
# Verifica que el .env existe
cat ../env

# O configura manualmente
export ANTHROPIC_API_KEY=sk-ant-...
export OPENAI_API_KEY=sk-proj-...
```

### Error: "Archivo no encontrado"

Verifica la ruta del archivo `_chat.txt` en `run_test.py`:

```python
CHAT_FILE = r"C:\Users\Cristhian\Documents\Programacion\whatsappbot\whatsappbot\tests\Mensajes Grupo Whatsapp\WhatsApp Chat - Migración SAP S_4 Hana\_chat.txt"
```

### Timeout o errores de API

- Claude/OpenAI podrían tener rate limits
- El script usa paralelismo con ThreadPool
- Si hay muchos errores, reduce paralelismo o añade delay

## Próximos Pasos

Una vez validado el sistema:

1. ✅ Calcular accuracy con validación manual
2. ✅ Ajustar prompts si es necesario
3. ✅ Integrar con `classifier-service` completo
4. ✅ Conectar con WhatsApp service
5. ✅ Conectar con Zoho Desk para crear tickets

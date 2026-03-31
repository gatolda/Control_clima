# Test Cases - Sensores (TC-SEN)

## TC-SEN-001: Lectura de temperatura (P0)
**Prerequisitos:** DHT22 conectado, app corriendo
**Pasos:**
1. Esperar ciclo de lectura (5 seg)
2. Verificar /sensores retorna temperatura != null
3. Verificar valor en rango razonable (15-40 C para invernadero)
4. Verificar dashboard muestra el valor
**Resultado esperado:** Temperatura valida mostrada en dashboard

## TC-SEN-002: Lectura de humedad (P0)
**Prerequisitos:** DHT22 conectado, app corriendo
**Pasos:**
1. Esperar ciclo de lectura
2. Verificar /sensores retorna humedad != null
3. Verificar valor en rango 20-90%
**Resultado esperado:** Humedad valida

## TC-SEN-003: Lectura de CO2 (P0)
**Prerequisitos:** MH-Z19 conectado, app corriendo
**Pasos:**
1. Esperar ciclo de lectura
2. Verificar /sensores retorna co2 != null
3. Verificar valor en rango 300-2000 ppm
**Resultado esperado:** CO2 valido

## TC-SEN-004: Filtro de lecturas erraticas - temperatura 0 (P0)
**Descripcion:** El DHT22 a veces retorna 0 cuando falla
**Pasos:**
1. Observar logs del servidor durante 10 minutos
2. Si aparece temp=0 o temp=None, verificar que:
   - No se guarda en la DB con valor 0
   - El sparkline no muestra pico a 0
   - El dashboard mantiene ultima lectura valida
**Resultado esperado:** Lecturas fallidas descartadas silenciosamente

## TC-SEN-005: Filtro de lecturas fuera de rango (P1)
**Pasos:**
1. Verificar que temp > 80 se descarta
2. Verificar que hum > 100 se descarta
3. Verificar que co2 > 5000 se descarta
4. Verificar que valores negativos se descartan
**Resultado esperado:** Solo valores en rango valido se guardan

## TC-SEN-006: Actualizacion en tiempo real via SocketIO (P1)
**Prerequisitos:** Dashboard abierto
**Pasos:**
1. Observar que los valores de sensores se actualizan cada 5 segundos
2. Verificar que no se necesita refrescar la pagina
3. Verificar que los gauges y valores numericos se actualizan
**Resultado esperado:** Datos en tiempo real sin refresh

## TC-SEN-007: Sparkline 24h sin picos erraticos (P1)
**Prerequisitos:** Al menos 1 hora de datos
**Pasos:**
1. Observar sparkline de temperatura en dashboard
2. Verificar que no hay picos abruptos a 0
3. Verificar que min/max mostrado es coherente
**Resultado esperado:** Grafico suave sin artifacts

## TC-SEN-008: Sensor health endpoint (P2)
**Pasos:**
1. GET /api/sensor-health
2. Verificar que retorna estado de cada sensor
3. Verificar campos: health, readings
**Resultado esperado:** JSON con estado de salud de cada sensor

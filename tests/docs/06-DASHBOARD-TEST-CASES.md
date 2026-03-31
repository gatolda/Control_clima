# Test Cases - Dashboard (TC-DSH)

## TC-DSH-001: Carga inicial del dashboard (P1)
**Pasos:**
1. Login y acceder a /
2. Verificar que se muestran 3 tarjetas de sensores (Temp, Hum, CO2)
3. Verificar que se muestra grid de actuadores
4. Verificar que se carga el chart de historial 24h
**Resultado esperado:** Dashboard completo renderizado

## TC-DSH-002: Indicador de estado OPTIMO/ALERTA (P1)
**Prerequisitos:** Umbrales configurados para la etapa actual
**Pasos:**
1. Verificar que cada sensor muestra badge de estado
2. Si valor esta en rango optimo -> muestra "OPTIMO" (verde)
3. Si valor esta fuera de rango -> muestra alerta
**Resultado esperado:** Badges reflejan estado real vs umbrales

## TC-DSH-003: Toggle actuador desde dashboard (P0)
**Pasos:**
1. Click en boton de un actuador (ej: ventiladores)
2. Verificar que cambia visualmente a estado ON
3. Verificar que el rele fisico se activa
4. Click de nuevo
5. Verificar estado OFF
**Resultado esperado:** Toggle bidireccional funcional

## TC-DSH-004: Alerta de conflicto en dashboard (P0)
**Pasos:**
1. Activar calefactor
2. Intentar activar aire_acondicionado
3. Verificar que aparece toast/alerta de conflicto
4. Verificar que AC no se activo
**Resultado esperado:** Alerta visible, accion bloqueada

## TC-DSH-005: Navegacion entre paginas (P2)
**Pasos:**
1. Desde dashboard, navegar a Diagnostics
2. Verificar que carga correctamente
3. Navegar a Settings
4. Verificar que carga correctamente
5. Volver a Dashboard
**Resultado esperado:** Navegacion fluida entre las 3 paginas

## TC-DSH-006: Reconexion SocketIO (P1)
**Pasos:**
1. Dashboard abierto y recibiendo datos
2. Desconectar red brevemente (apagar wifi 5 seg)
3. Reconectar red
4. Verificar que dashboard retoma datos en tiempo real
**Resultado esperado:** Reconexion automatica sin recargar pagina

## TC-DSH-007: Pagina de diagnosticos (P2)
**Pasos:**
1. Acceder a /diagnostics
2. Verificar tarjetas de salud de sensores
3. Verificar tabla de lecturas detalladas
4. Verificar log de eventos de actuadores
**Resultado esperado:** Datos de diagnostico coherentes

## TC-DSH-008: Responsive en movil (P2)
**Pasos:**
1. Acceder al dashboard desde celular
2. Verificar que las tarjetas se reorganizan
3. Verificar que los controles son tocables
4. Verificar que el texto es legible
**Resultado esperado:** Usable en pantalla movil

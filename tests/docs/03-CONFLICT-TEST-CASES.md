# Test Cases - Conflictos y Seguridad (TC-CON)

## TC-CON-001: Calefactor bloquea aire acondicionado (P0)
**Prerequisitos:** App corriendo, todo apagado
**Pasos:**
1. Activar "calefactor" -> debe funcionar
2. Intentar activar "aire_acondicionado"
3. Verificar que se recibe alerta de conflicto
4. Verificar que aire_acondicionado NO se activa
5. Verificar que calefactor sigue activo
**Resultado esperado:** AC bloqueado, alerta mostrada en dashboard

## TC-CON-002: Aire acondicionado bloquea calefactor (P0)
**Prerequisitos:** App corriendo, todo apagado
**Pasos:**
1. Activar "aire_acondicionado" -> debe funcionar
2. Intentar activar "calefactor"
3. Verificar que se recibe alerta de conflicto
4. Verificar que calefactor NO se activa
**Resultado esperado:** Calefactor bloqueado, alerta mostrada

## TC-CON-003: Humidificador bloquea deshumidificador (P0)
**Prerequisitos:** App corriendo, todo apagado
**Pasos:**
1. Activar "humidificador" -> debe funcionar
2. Intentar activar "deshumidificador"
3. Verificar que se recibe alerta de conflicto
**Resultado esperado:** Deshumidificador bloqueado

## TC-CON-004: Deshumidificador bloquea humidificador (P0)
**Prerequisitos:** App corriendo, todo apagado
**Pasos:**
1. Activar "deshumidificador"
2. Intentar activar "humidificador"
3. Verificar alerta de conflicto
**Resultado esperado:** Humidificador bloqueado

## TC-CON-005: Desactivar primero permite activar segundo (P0)
**Prerequisitos:** Calefactor activo
**Pasos:**
1. Desactivar "calefactor"
2. Activar "aire_acondicionado"
3. Verificar que AC se activa correctamente
**Resultado esperado:** AC activado sin conflicto

## TC-CON-006: Actuadores sin conflicto coexisten (P1)
**Prerequisitos:** Todo apagado
**Pasos:**
1. Activar "ventiladores" + "luz" + "intractor" + "filtro_carbon"
2. Verificar que los 4 estan activos simultaneamente
3. Verificar que no hay alertas de conflicto
**Resultado esperado:** 4 actuadores coexisten sin problema

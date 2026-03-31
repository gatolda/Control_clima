# Test Cases - Autenticacion (TC-AUT)

## TC-AUT-001: Login exitoso (P0)
**Pasos:**
1. Navegar a /login
2. Ingresar usuario y password correctos
3. Verificar redireccion al dashboard
4. Verificar que muestra contenido protegido
**Resultado esperado:** Login exitoso, acceso al dashboard

## TC-AUT-002: Login fallido - password incorrecto (P0)
**Pasos:**
1. Navegar a /login
2. Ingresar usuario correcto, password incorrecto
3. Verificar mensaje de error
4. Verificar que NO redirige al dashboard
**Resultado esperado:** Error mostrado, sin acceso

## TC-AUT-003: Login fallido - usuario inexistente (P0)
**Pasos:**
1. Navegar a /login
2. Ingresar usuario "hacker", cualquier password
3. Verificar mensaje de error generico (no revela si usuario existe)
**Resultado esperado:** Mismo mensaje de error que TC-AUT-002

## TC-AUT-004: Rutas protegidas sin login (P0)
**Pasos:**
1. Sin sesion activa, intentar acceder a:
   - / (dashboard)
   - /diagnostics
   - /settings
   - /sensores
   - /actuadores/estado
   - /api/history
   - /api/config
2. Verificar redireccion a /login en todos los casos
**Resultado esperado:** Todas las rutas redirigen a login

## TC-AUT-005: Logout (P1)
**Pasos:**
1. Login exitoso
2. Navegar a /logout
3. Verificar redireccion a /login
4. Intentar acceder a /dashboard
5. Verificar que redirige a /login
**Resultado esperado:** Sesion terminada, acceso revocado

## TC-AUT-006: Remember me - persistencia de sesion (P2)
**Pasos:**
1. Login exitoso (remember=True por defecto)
2. Cerrar navegador
3. Abrir navegador y acceder al dashboard
4. Verificar que sigue autenticado
**Resultado esperado:** Sesion persiste entre cierres de navegador

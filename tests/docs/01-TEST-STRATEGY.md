# QA Test Strategy - Control Climatico Invernadero

## Sistema bajo prueba
- **Plataforma:** Raspberry Pi + Flask + SocketIO
- **Hardware:** 8 reles (activo_bajo), DHT22, MH-Z19 CO2
- **Acceso:** Dashboard web con autenticacion

## Categorias de prueba

| Cat | ID Prefix | Descripcion | Tests | Prioridad |
|-----|-----------|-------------|-------|-----------|
| Reles | TC-REL | Control de reles GPIO | 12 | P0-P1 |
| Sensores | TC-SEN | Lecturas y validacion | 8 | P0-P1 |
| Conflictos | TC-CON | Pares excluyentes y seguridad | 6 | P0 |
| Auth | TC-AUT | Autenticacion y sesiones | 6 | P0-P1 |
| Dashboard | TC-DSH | Frontend y tiempo real | 8 | P1-P2 |
| API | TC-API | Endpoints HTTP | 6 | P1 |
| Database | TC-DB | Almacenamiento y consultas | 4 | P2 |
| **Total** | | | **50** | |

## Quality Gates

| Gate | Target | Blocker |
|------|--------|---------|
| Tests ejecutados | 100% | Si |
| Pass rate | >= 90% | Si |
| P0 bugs abiertos | 0 | Si |
| P1 bugs abiertos | <= 3 | Si |
| Conflictos verificados | 100% | Si |

## Entorno de pruebas

- **Pi (hardware real):** Tests de reles, sensores, GPIO
- **Windows (preview_server):** Tests de dashboard, auth, API
- **Ambos:** Tests de integracion end-to-end

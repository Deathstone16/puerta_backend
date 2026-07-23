# Plan de implementación — Mejoras UX del Login

## Resumen

Mejorar la pantalla de login con selector visual de rol, bullets dinámicos según rol seleccionado, y eliminación de jerga técnica.

---

## Tareas

- [ ] 1. Agregar selector de rol al LoginPage
  - 4 botones/tabs horizontales debajo del título: Dueño, RRPP, Guardia, Cajera
  - Cada uno con un ícono representativo y un color accent
  - Estado seleccionado cambia visual (border + bg tint)
  - State: `const [selectedRole, setSelectedRole] = useState('dueno')`
  - No afecta la lógica de login (es solo visual/contextual)
  - _Requisito 1.1–1.5_

- [ ] 2. Definir contenido por rol
  - Crear objeto/mapa con la info de cada rol:
    ```jsx
    const ROLE_CONTEXT = {
      dueno: {
        label: 'Dueño',
        icon: 'settings',
        color: 'text-uv',
        subtitle: 'Gestioná tus eventos y tu equipo.',
        bullets: [
          'Métricas y recaudación en tiempo real',
          'Gestión de RRPP, guardias y cajeras',
          'Control total de tus noches',
        ],
      },
      rrpp: {
        label: 'RRPP',
        icon: 'users',
        color: 'text-strobe',
        subtitle: 'Gestioná tus listas e invitados.',
        bullets: [
          'Listas de invitados por evento',
          'Seguimiento de anotados e ingresados',
          'Comisiones por noche',
        ],
      },
      guardia: {
        label: 'Guardia',
        icon: 'shield',
        color: 'text-cyan-400',
        subtitle: 'Controlá el acceso de la noche.',
        bullets: [
          'Escaneo de QR en puerta',
          'Aprobación y rechazo de acceso',
          'Aforo en vivo',
        ],
      },
      cajera: {
        label: 'Cajera',
        icon: 'cash',
        color: 'text-emerald-400',
        subtitle: 'Cobrá y registrá ingresos.',
        bullets: [
          'Cobro por efectivo o transferencia',
          'Validación de entradas web',
          'Registro de ventas en puerta',
        ],
      },
    }
    ```
  - _Requisitos 3.1–3.5, 4.1–4.4_

- [ ] 3. Actualizar panel izquierdo con bullets dinámicos
  - Reemplazar los 3 bullets estáticos actuales por `ROLE_CONTEXT[selectedRole].bullets`
  - Mantener los dots con el color del rol seleccionado
  - Transición suave: usar CSS transition en opacity/transform
  - _Requisito 3.5_

- [ ] 4. Actualizar subtítulo del formulario
  - Reemplazar "Ingresá con las credenciales asignadas a tu rol" por `ROLE_CONTEXT[selectedRole].subtitle`
  - _Requisito 4.1–4.4_

- [ ] 5. Limpiar footer
  - Eliminar "Sesión segura · tokens temporales / No se almacenan credenciales"
  - Reemplazar con: "Tus datos están protegidos" o simplemente dejar solo el borde superior sin texto
  - _Requisito 2.1–2.3_

- [ ] 6. Verificación visual
  - Verificar que en desktop el panel izquierdo cambia bullets al seleccionar rol
  - Verificar que en mobile el selector se ve bien (horizontal scroll si es necesario)
  - Verificar que el login funciona igual sin importar qué rol esté seleccionado
  - Verificar que la redirección post-login sigue yendo al dashboard correcto del JWT

---

## Notas

- El selector de rol es SOLO visual/contextual. No envía nada al backend ni afecta la autenticación.
- Si un guardia selecciona "Dueño" y se loguea con credenciales de guardia, va a ir a `/guardia` igual — el JWT manda.
- El propósito es dar contexto y confianza al usuario de que está entrando al lugar correcto.
- Los colores del selector (uv, strobe, cyan, emerald) mantienen coherencia con los colores usados en cada dashboard.

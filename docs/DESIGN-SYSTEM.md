# Norware — Sistema de Diseño

Este documento define los tokens de diseño y componentes de firma de la plataforma. Es la fuente de verdad para coordinar entre el equipo de backend (serializers, campos de color/estado) y el equipo de frontend (Tailwind, componentes React).

> El frontend vive en un repositorio separado. Este documento existe aquí para que el backend sepa qué valores de datos espera el frontend y pueda validarlos correctamente.

---

## 1. Paleta de colores

La identidad visual sale del mundo real del boliche: fondo oscuro con dos luces cruzadas (violeta + cian). No es un solo acento neón — son dos fuentes de luz distintas.

| Token | Valor HEX | Uso |
|-------|-----------|-----|
| `--void` | `#0A0A10` | Fondo base de toda la app |
| `--floor` | `#141220` | Superficies elevadas: cards, modales, dashboards |
| `--uv` | `#8B5CF6` | Violeta blacklight — acento principal, CTAs, estado aprobado |
| `--strobe` | `#22D3EE` | Cian frío — datos en vivo, contadores, analíticas |
| `--door-red` | `#E23B5A` | Alertas críticas: rebotado, agotado, error, cancelado |
| `--paper-text` | `#EDEBF5` | Texto principal sobre fondos oscuros |
| `--muted` | `#8A87A3` | Texto secundario, labels, metadata |

**Configuración Tailwind (`tailwind.config.js`):**

```js
theme: {
  extend: {
    colors: {
      'void':       '#0A0A10',
      'floor':      '#141220',
      'uv':         '#8B5CF6',
      'strobe':     '#22D3EE',
      'door-red':   '#E23B5A',
      'paper-text': '#EDEBF5',
      'muted':      '#8A87A3',
    }
  }
}
```

### Colores de estado del Asistente

| Estado | Color | Token |
|--------|-------|-------|
| `pendiente` | Muted gris | `--muted` |
| `aprobado_guardia` | Violeta | `--uv` |
| `rebotado_guardia` | Rojo | `--door-red` |
| `ingresado_final` | Cian | `--strobe` |
| Evento cancelado | Rojo | `--door-red` |

---

## 2. Tipografía

Tres familias con roles distintos — no mezclar fuera de su contexto.

| Familia | Fuentes | Uso |
|---------|---------|-----|
| Display | Archivo Black, Unbounded | Títulos, nombre del evento, número de aforo. Siempre en mayúsculas en títulos grandes. |
| Body | Inter, General Sans | Texto corrido, labels, descripciones |
| Mono | Space Mono, IBM Plex Mono | Precios, DNI, horarios, códigos, contadores en vivo |

**Configuración Tailwind:**

```js
theme: {
  extend: {
    fontFamily: {
      'display': ['Archivo Black', 'Unbounded', 'sans-serif'],
      'body':    ['Inter', 'General Sans', 'sans-serif'],
      'mono':    ['Space Mono', 'IBM Plex Mono', 'monospace'],
    }
  }
}
```

**Reglas:**
- El nombre del evento: `font-display uppercase tracking-tight`
- Precio publicado: `font-mono text-paper-text`
- DNI en pantalla de guardia/cajera: `font-mono text-2xl`
- Horarios y timestamps: `font-mono text-muted`

---

## 3. Forma y bordes

Escala de 8px. Dos valores de border-radius con semántica clara:

| Token | Valor | Uso |
|-------|-------|-----|
| `physical` | `0px` | Elementos que representan objetos físicos: pulsera, sello de tinta |
| `interface` | `12px` | Elementos de interfaz digital: cards, botones, modales, inputs |

Sin sombras difusas. Sin glassmorphism. Sin `backdrop-blur`.

**Configuración Tailwind:**

```js
theme: {
  extend: {
    borderRadius: {
      'physical':  '0px',
      'interface': '12px',
    }
  }
}
```

---

## 4. Componentes de firma

Estos dos componentes son la identidad visual de la plataforma. Aparecen en momentos específicos — no son decorativos.

### `<Pulsera color />`

Representa la pulsera física que se entrega en la puerta. El color del evento es un dato real que viene del backend (`Evento.color_pulsera`).

**Cuándo aparece:**
- Card del evento en la cartelera
- Detalle del evento
- Wallet del cliente (ticket)
- Pantalla de confirmación de cajera ("Entregar pulsera [color]")
- Dashboard del dueño al crear/editar evento (preview en vivo)

**Especificación visual:**
- Franja horizontal sólida
- `border-radius: 0px` (es un objeto físico)
- Color de fondo = `Evento.color_pulsera` (puede ser nombre CSS o hex)
- Texto explícito adentro: `"Pulsera [color] esta noche"`
- Fuente: `font-mono` o `font-body` en mayúsculas
- Borde recto, sin sombra

**Qué devuelve el backend:** el campo `color_pulsera` en el serializer de Evento es un string libre. Ejemplos válidos: `"violeta"`, `"roja"`, `"verde fluo"`, `"#FF6B00"`. El frontend es responsable de interpretar ese string como color CSS.

---

### `<Sello estado />`

Representa el sello de tinta del boliche — marca de ingreso o rechazo. Es irregular (no un círculo perfecto), con rotación leve, como un sello real.

**Cuándo aparece:**
- Pantalla del guardia después de aprobar/rebotar
- Wallet del cliente (estado del ticket)
- Vista de evento cancelado

**NO aparece:**
- En cards de la cartelera (solo la pulsera)
- Como elemento decorativo sin dato real

**Estados y colores:**

| Estado | Texto del sello | Color |
|--------|----------------|-------|
| `aprobado_guardia` | "APROBADO" | `--uv` |
| `rebotado_guardia` | "RECHAZADO" | `--door-red` |
| `ingresado_final` | "INGRESADO" | `--strobe` |
| `cancelado` (evento) | "CANCELADO" | `--door-red` |
| `devolucion` (wallet cancelado) | "DEVOLUCIÓN EN PROCESO" | `--door-red` |

**Especificación visual:**
- SVG con forma levemente irregular (no círculo perfecto — simular sello de goma)
- Rotación: `-8deg` a `+8deg` aleatoria o fija por estado
- `border-radius: 0px` o borde en el SVG sin radius
- Sin relleno sólido — borde del sello grueso, texto en el centro
- Opacidad del SVG: 90% (para que se vea como tinta, no como vector perfecto)

---

## 5. Componente `<AforoLive />`

Contador de aforo en tiempo real. Aparece en guardia, cajera, y dashboard del dueño.

**Especificación:**
- Número grande en `font-display` (Archivo Black)
- Color del número: `--strobe` (dato en vivo)
- Formato: `342 / 800`
- Debajo: barra de progreso del porcentaje (`--strobe` sobre `--floor`)
- Polling cada 4 segundos a `GET /api/dashboard/aforo/:evento_id/`
- Pulsa visualmente al actualizarse (transición de opacidad breve)

**Qué devuelve el backend:**
```json
{
  "ingresados": 342,
  "aforo_max":  800,
  "porcentaje": 42.75,
  "pendientes": 58
}
```

---

## 6. Pantallas y contexto de diseño

### Pantallas mobile-first estricto (una mano, poca luz)
- `/guardia` — botones full-width gigantes, mínimo texto, máximo contraste
- `/cajera` — tabs simples, botones grandes, confirmación con pulsera visible

### Pantallas tablet/desktop
- `/dashboard` — métricas densas, tablas, formularios de configuración
- `/rrpp` — panel con links, estadísticas

### Pantallas públicas
- `/` — cartelera, fondo ASCII animado solo en esta ruta
- `/evento/:id` — detalle, checkout
- `/wallet/:token` — ticket del cliente, mobile-optimized
- `/lista/:slug` — formulario de anotación

---

## 7. Lo que NO va en este sistema

Para mantener la identidad visual:

- Sin sombras difusas (`box-shadow` con blur alto)
- Sin glassmorphism (`backdrop-filter: blur`)
- Sin fondo crema, serif, o terracota
- Sin negro plano con un solo acento neón (siempre dos luces: `--uv` + `--strobe`)
- Sin marquesinas de recital, guitarra, o estética de teatro
- Sin lorem ipsum ni fotos de stock genéricas
- Sin numeración decorativa sin dato real asociado
- Sin usar `--uv` y `--strobe` al mismo tiempo en el mismo elemento (son dos fuentes de luz distintas, no se mezclan)

---

## 8. Fondo ASCII animado

Solo en la ruta `/` (landing pública). **No cargar en `/guardia` ni `/cajera`** — consume CPU y batería que necesita el lector QR.

**Implementación:** componente `<AsciiBackground />` en React, capa `position: fixed; inset: 0; z-index: -1; pointer-events: none`. Canvas 2D.

**Parámetros:**

```json
{
  "renderMode":  "dither",
  "bgMode":      "solid",
  "bgBlur":      12,
  "bgOpacity":   100,
  "cellSize":    10,
  "coverage":    36,
  "invert":      false,
  "styleBlend":  "screen",
  "charSet":     "binary",
  "brightness":  0,
  "contrast":    115,
  "edgeEmphasis":40,
  "density":     0,
  "tint":        "#8B5CF6",
  "tintOpacity": 45,
  "overlayBlend":"overlay",
  "saturation":  100,
  "pfx": {
    "vignette":  { "enabled": true, "intensity": 38 },
    "scanLines": { "enabled": true, "intensity": 28 },
    "chromatic": { "enabled": true, "intensity": 40 },
    "bloom":     { "enabled": true, "intensity": 60 },
    "filmGrain": { "enabled": true, "intensity": 40 },
    "glitch":    { "enabled": true, "intensity": 20 }
  },
  "animated":        true,
  "animStyle":       "flicker",
  "animSpeed":       { "enabled": true, "intensity": 100 },
  "animIntensity":   { "enabled": true, "intensity": 60 }
}
```

**Requisitos:**
- Respetar `prefers-reduced-motion` — frame estático si el usuario lo pide
- Pausar `requestAnimationFrame` cuando `document.hidden` (tab no visible)
- Imagen fuente oscura con luces violeta/cian en `/public/ascii-source.webp`

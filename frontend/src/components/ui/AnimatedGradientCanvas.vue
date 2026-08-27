<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

const PATTERN_SHAPES = {
  Checks: 0,
  Stripes: 1,
  Edge: 2,
} as const

type PatternShape = keyof typeof PATTERN_SHAPES

type PresetName = 'Prism' | 'Lava' | 'Plasma' | 'Pulse' | 'Vortex' | 'Mist'

interface PresetParams {
  color1: string
  color2: string
  color3: string
  rotation: number
  proportion: number
  scale: number
  speed: number
  distortion: number
  swirl: number
  swirlIterations: number
  softness: number
  offset: number
  shape: PatternShape
  shapeSize: number
}

interface CustomConfig {
  preset: 'custom'
  color1: string
  color2: string
  color3: string
  rotation?: number
  proportion?: number
  scale?: number
  speed?: number
  distortion?: number
  swirl?: number
  swirlIterations?: number
  softness?: number
  offset?: number
  shape?: PatternShape
  shapeSize?: number
}

interface PresetConfig {
  preset: PresetName
  speed?: number
}

type GradientConfig = CustomConfig | PresetConfig

const presets: Record<PresetName, PresetParams> = {
  Prism: {
    color1: '#050505',
    color2: '#66B3FF',
    color3: '#FFFFFF',
    rotation: -50,
    proportion: 1,
    scale: 0.01,
    speed: 30,
    distortion: 0,
    swirl: 50,
    swirlIterations: 16,
    softness: 47,
    offset: -299,
    shape: 'Checks',
    shapeSize: 45,
  },
  Lava: {
    color1: '#FF9F21',
    color2: '#FF0303',
    color3: '#000000',
    rotation: 114,
    proportion: 100,
    scale: 0.52,
    speed: 30,
    distortion: 7,
    swirl: 18,
    swirlIterations: 20,
    softness: 100,
    offset: 717,
    shape: 'Edge',
    shapeSize: 12,
  },
  Plasma: {
    color1: '#B566FF',
    color2: '#000000',
    color3: '#000000',
    rotation: 0,
    proportion: 63,
    scale: 0.75,
    speed: 30,
    distortion: 5,
    swirl: 61,
    swirlIterations: 5,
    softness: 100,
    offset: -168,
    shape: 'Checks',
    shapeSize: 28,
  },
  Pulse: {
    color1: '#66FF85',
    color2: '#000000',
    color3: '#000000',
    rotation: -167,
    proportion: 92,
    scale: 0,
    speed: 20,
    distortion: 54,
    swirl: 75,
    swirlIterations: 3,
    softness: 28,
    offset: -813,
    shape: 'Checks',
    shapeSize: 79,
  },
  Vortex: {
    color1: '#000000',
    color2: '#FFFFFF',
    color3: '#000000',
    rotation: 50,
    proportion: 41,
    scale: 0.4,
    speed: 20,
    distortion: 0,
    swirl: 100,
    swirlIterations: 3,
    softness: 5,
    offset: -744,
    shape: 'Stripes',
    shapeSize: 80,
  },
  Mist: {
    color1: '#050505',
    color2: '#FF66B8',
    color3: '#050505',
    rotation: 0,
    proportion: 33,
    scale: 0.48,
    speed: 39,
    distortion: 4,
    swirl: 65,
    swirlIterations: 5,
    softness: 100,
    offset: -235,
    shape: 'Edge',
    shapeSize: 48,
  },
}

const props = withDefaults(
  defineProps<{
    config?: GradientConfig
    radius?: string
    className?: string
  }>(),
  {
    config: () => ({ preset: 'Prism' as const }),
    radius: '0px',
    className: '',
  },
)

const containerRef = ref<HTMLDivElement | null>(null)
const canvasRef = ref<HTMLCanvasElement | null>(null)
const webglAvailable = ref(true)

let frameId: number | null = null
let resizeObserver: ResizeObserver | null = null
let gl: WebGL2RenderingContext | null = null
let program: WebGLProgram | null = null
let vertexShader: WebGLShader | null = null
let fragmentShader: WebGLShader | null = null
let positionBuffer: WebGLBuffer | null = null
let startTime = 0

const params = computed<PresetParams>(() => {
  const config = props.config
  if (config.preset === 'custom') {
    return {
      color1: config.color1,
      color2: config.color2,
      color3: config.color3,
      rotation: config.rotation ?? 0,
      proportion: config.proportion ?? 35,
      scale: config.scale ?? 1,
      speed: config.speed ?? 25,
      distortion: config.distortion ?? 12,
      swirl: config.swirl ?? 80,
      swirlIterations: config.swirlIterations ?? 10,
      softness: config.softness ?? 100,
      offset: config.offset ?? 0,
      shape: config.shape ?? 'Checks',
      shapeSize: config.shapeSize ?? 10,
    }
  }

  const preset = presets[config.preset] || presets.Prism
  return {
    ...preset,
    speed: config.speed ?? preset.speed,
  }
})

function cleanup() {
  if (frameId != null) {
    cancelAnimationFrame(frameId)
    frameId = null
  }
  resizeObserver?.disconnect()
  resizeObserver = null

  if (gl) {
    if (program) gl.deleteProgram(program)
    if (vertexShader) gl.deleteShader(vertexShader)
    if (fragmentShader) gl.deleteShader(fragmentShader)
    if (positionBuffer) gl.deleteBuffer(positionBuffer)
  }

  gl = null
  program = null
  vertexShader = null
  fragmentShader = null
  positionBuffer = null
}

function createShader(context: WebGL2RenderingContext, type: number, source: string) {
  const shader = context.createShader(type)
  if (!shader) return null
  context.shaderSource(shader, source)
  context.compileShader(shader)
  if (!context.getShaderParameter(shader, context.COMPILE_STATUS)) {
    console.error(context.getShaderInfoLog(shader))
    context.deleteShader(shader)
    return null
  }
  return shader
}

function createProgram(context: WebGL2RenderingContext, vs: WebGLShader, fs: WebGLShader) {
  const nextProgram = context.createProgram()
  if (!nextProgram) return null
  context.attachShader(nextProgram, vs)
  context.attachShader(nextProgram, fs)
  context.linkProgram(nextProgram)
  if (!context.getProgramParameter(nextProgram, context.LINK_STATUS)) {
    console.error(context.getProgramInfoLog(nextProgram))
    context.deleteProgram(nextProgram)
    return null
  }
  return nextProgram
}

function resizeCanvas() {
  if (!canvasRef.value || !containerRef.value || !gl) return
  const width = containerRef.value.clientWidth
  const height = containerRef.value.clientHeight
  const pixelRatio = window.devicePixelRatio || 1
  canvasRef.value.width = Math.max(1, Math.floor(width * pixelRatio))
  canvasRef.value.height = Math.max(1, Math.floor(height * pixelRatio))
  canvasRef.value.style.width = `${width}px`
  canvasRef.value.style.height = `${height}px`
  gl.viewport(0, 0, canvasRef.value.width, canvasRef.value.height)
}

function startRendering() {
  cleanup()

  if (!canvasRef.value || !containerRef.value) return

  gl = canvasRef.value.getContext('webgl2', {
    premultipliedAlpha: true,
    alpha: true,
    antialias: true,
  })

  if (!gl) {
    webglAvailable.value = false
    return
  }

  webglAvailable.value = true

  vertexShader = createShader(gl, gl.VERTEX_SHADER, VERTEX_SHADER)
  fragmentShader = createShader(gl, gl.FRAGMENT_SHADER, FRAGMENT_SHADER)
  if (!vertexShader || !fragmentShader) {
    webglAvailable.value = false
    cleanup()
    return
  }

  program = createProgram(gl, vertexShader, fragmentShader)
  if (!program) {
    webglAvailable.value = false
    cleanup()
    return
  }

  gl.useProgram(program)

  positionBuffer = gl.createBuffer()
  gl.bindBuffer(gl.ARRAY_BUFFER, positionBuffer)
  gl.bufferData(
    gl.ARRAY_BUFFER,
    new Float32Array([-1, -1, 1, -1, -1, 1, -1, 1, 1, -1, 1, 1]),
    gl.STATIC_DRAW,
  )

  const positionLocation = gl.getAttribLocation(program, 'a_position')
  gl.enableVertexAttribArray(positionLocation)
  gl.vertexAttribPointer(positionLocation, 2, gl.FLOAT, false, 0, 0)

  const uniforms = {
    time: gl.getUniformLocation(program, 'u_time'),
    resolution: gl.getUniformLocation(program, 'u_resolution'),
    pixelRatio: gl.getUniformLocation(program, 'u_pixelRatio'),
    scale: gl.getUniformLocation(program, 'u_scale'),
    rotation: gl.getUniformLocation(program, 'u_rotation'),
    color1: gl.getUniformLocation(program, 'u_color1'),
    color2: gl.getUniformLocation(program, 'u_color2'),
    color3: gl.getUniformLocation(program, 'u_color3'),
    proportion: gl.getUniformLocation(program, 'u_proportion'),
    softness: gl.getUniformLocation(program, 'u_softness'),
    shape: gl.getUniformLocation(program, 'u_shape'),
    shapeScale: gl.getUniformLocation(program, 'u_shapeScale'),
    distortion: gl.getUniformLocation(program, 'u_distortion'),
    swirl: gl.getUniformLocation(program, 'u_swirl'),
    swirlIterations: gl.getUniformLocation(program, 'u_swirlIterations'),
  }

  resizeCanvas()
  resizeObserver = new ResizeObserver(resizeCanvas)
  resizeObserver.observe(containerRef.value)

  startTime = performance.now()

  const render = (time: number) => {
    if (!gl || !canvasRef.value) return

    const elapsed = (time - startTime) / 1000
    const speed = (params.value.speed / 100) * 5
    const c1 = hexToRgba(params.value.color1)
    const c2 = hexToRgba(params.value.color2)
    const c3 = hexToRgba(params.value.color3)

    gl.uniform1f(uniforms.time, elapsed * speed + params.value.offset * 0.01)
    gl.uniform2f(uniforms.resolution, canvasRef.value.width, canvasRef.value.height)
    gl.uniform1f(uniforms.pixelRatio, window.devicePixelRatio || 1)
    gl.uniform1f(uniforms.scale, params.value.scale)
    gl.uniform1f(uniforms.rotation, (params.value.rotation * Math.PI) / 180)
    gl.uniform4f(uniforms.color1, c1[0], c1[1], c1[2], c1[3])
    gl.uniform4f(uniforms.color2, c2[0], c2[1], c2[2], c2[3])
    gl.uniform4f(uniforms.color3, c3[0], c3[1], c3[2], c3[3])
    gl.uniform1f(uniforms.proportion, params.value.proportion / 100)
    gl.uniform1f(uniforms.softness, params.value.softness / 100)
    gl.uniform1f(uniforms.shape, PATTERN_SHAPES[params.value.shape])
    gl.uniform1f(uniforms.shapeScale, params.value.shapeSize / 100)
    gl.uniform1f(uniforms.distortion, params.value.distortion / 50)
    gl.uniform1f(uniforms.swirl, params.value.swirl / 100)
    gl.uniform1f(uniforms.swirlIterations, params.value.swirl === 0 ? 0 : params.value.swirlIterations)
    gl.drawArrays(gl.TRIANGLES, 0, 6)

    frameId = requestAnimationFrame(render)
  }

  frameId = requestAnimationFrame(render)
}

onMounted(startRendering)
onBeforeUnmount(cleanup)
watch(params, startRendering, { deep: true })
</script>

<template>
  <div ref="containerRef" class="animated-gradient" :class="className" :style="{ borderRadius: radius }" aria-hidden="true">
    <canvas ref="canvasRef" class="animated-gradient__canvas" />
    <div v-if="!webglAvailable" class="animated-gradient__fallback" />
  </div>
</template>

<style scoped>
.animated-gradient {
  position: absolute;
  inset: 0;
  overflow: hidden;
}

.animated-gradient__canvas,
.animated-gradient__fallback {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}

.animated-gradient__canvas {
  display: block;
}

.animated-gradient__fallback {
  background:
    radial-gradient(circle at 20% 30%, rgba(0, 117, 255, 0.3), transparent 24%),
    radial-gradient(circle at 78% 24%, rgba(33, 212, 253, 0.18), transparent 22%),
    linear-gradient(140deg, var(--color-bg-surface) 0%, var(--color-bg-elevated) 55%, var(--color-bg-base) 100%);
}
</style>

<script lang="ts">
const VERTEX_SHADER = `#version 300 es
in vec4 a_position;
void main() {
  gl_Position = a_position;
}`

const FRAGMENT_SHADER = `#version 300 es
precision highp float;

uniform float u_time;
uniform float u_pixelRatio;
uniform vec2 u_resolution;
uniform float u_scale;
uniform float u_rotation;
uniform vec4 u_color1;
uniform vec4 u_color2;
uniform vec4 u_color3;
uniform float u_proportion;
uniform float u_softness;
uniform float u_shape;
uniform float u_shapeScale;
uniform float u_distortion;
uniform float u_swirl;
uniform float u_swirlIterations;

out vec4 fragColor;

#define TWO_PI 6.28318530718
#define PI 3.14159265358979323846

vec2 rotate(vec2 uv, float th) {
  return mat2(cos(th), sin(th), -sin(th), cos(th)) * uv;
}

float random(vec2 st) {
  return fract(sin(dot(st.xy, vec2(12.9898, 78.233))) * 43758.5453123);
}

float noise(vec2 st) {
  vec2 i = floor(st);
  vec2 f = fract(st);
  float a = random(i);
  float b = random(i + vec2(1.0, 0.0));
  float c = random(i + vec2(0.0, 1.0));
  float d = random(i + vec2(1.0, 1.0));
  vec2 u = f * f * (3.0 - 2.0 * f);
  float x1 = mix(a, b, u.x);
  float x2 = mix(c, d, u.x);
  return mix(x1, x2, u.y);
}

vec4 blend_colors(vec4 c1, vec4 c2, vec4 c3, float mixer, float edgesWidth, float edge_blur) {
  vec3 color1 = c1.rgb * c1.a;
  vec3 color2 = c2.rgb * c2.a;
  vec3 color3 = c3.rgb * c3.a;

  float r1 = smoothstep(.0 + .35 * edgesWidth, .7 - .35 * edgesWidth + .5 * edge_blur, mixer);
  float r2 = smoothstep(.3 + .35 * edgesWidth, 1. - .35 * edgesWidth + edge_blur, mixer);

  vec3 blended_color_2 = mix(color1, color2, r1);
  float blended_opacity_2 = mix(c1.a, c2.a, r1);

  vec3 c = mix(blended_color_2, color3, r2);
  float o = mix(blended_opacity_2, c3.a, r2);
  return vec4(c, o);
}

void main() {
  vec2 uv = gl_FragCoord.xy / u_resolution.xy;
  float t = .5 * u_time;
  float noise_scale = .0005 + .006 * u_scale;

  uv -= .5;
  uv *= (noise_scale * u_resolution);
  uv = rotate(uv, u_rotation * .5 * PI);
  uv /= u_pixelRatio;
  uv += .5;

  float n1 = noise(uv * 1. + t);
  float n2 = noise(uv * 2. - t);
  float angle = n1 * TWO_PI;

  uv.x += 4. * u_distortion * n2 * cos(angle);
  uv.y += 4. * u_distortion * n2 * sin(angle);

  float iterations_number = ceil(clamp(u_swirlIterations, 1., 30.));
  for (float i = 1.; i <= 30.; i++) {
    if (i > iterations_number) {
      break;
    }
    uv.x += clamp(u_swirl, 0., 2.) / i * cos(t + i * 1.5 * uv.y);
    uv.y += clamp(u_swirl, 0., 2.) / i * cos(t + i * 1. * uv.x);
  }

  float proportion = clamp(u_proportion, 0., 1.);
  float shape = 0.;
  float mixer = 0.;

  if (u_shape < .5) {
    vec2 checks_shape_uv = uv * (.5 + 3.5 * u_shapeScale);
    shape = .5 + .5 * sin(checks_shape_uv.x) * cos(checks_shape_uv.y);
    mixer = shape + .48 * sign(proportion - .5) * pow(abs(proportion - .5), .5);
  } else if (u_shape < 1.5) {
    vec2 stripes_shape_uv = uv * (.25 + 3. * u_shapeScale);
    float f = fract(stripes_shape_uv.y);
    shape = smoothstep(.0, .55, f) * smoothstep(1., .45, f);
    mixer = shape + .48 * sign(proportion - .5) * pow(abs(proportion - .5), .5);
  } else {
    float sh = 1. - uv.y;
    sh -= .5;
    sh /= (noise_scale * u_resolution.y);
    sh += .5;
    float shape_scaling = .2 * (1. - u_shapeScale);
    shape = smoothstep(.45 - shape_scaling, .55 + shape_scaling, sh + .3 * (proportion - .5));
    mixer = shape;
  }

  vec4 color_mix = blend_colors(u_color1, u_color2, u_color3, mixer, 1. - clamp(u_softness, 0., 1.), .01 + .01 * u_scale);
  fragColor = vec4(color_mix.rgb, color_mix.a);
}`

function hexToRgba(input: string): [number, number, number, number] {
  let r = 0
  let g = 0
  let b = 0
  let a = 1

  if (input.startsWith('rgba(')) {
    const parts = input.slice(5, -1).split(',')
    r = parseInt(parts[0], 10) / 255
    g = parseInt(parts[1], 10) / 255
    b = parseInt(parts[2], 10) / 255
    a = parseFloat(parts[3])
  } else if (input.startsWith('rgb(')) {
    const parts = input.slice(4, -1).split(',')
    r = parseInt(parts[0], 10) / 255
    g = parseInt(parts[1], 10) / 255
    b = parseInt(parts[2], 10) / 255
  } else if (input.startsWith('hsla(') || input.startsWith('hsl(')) {
    const isHsla = input.startsWith('hsla(')
    const parts = input.slice(isHsla ? 5 : 4, -1).split(',')
    const h = parseFloat(parts[0]) / 360
    const s = parseFloat(parts[1]) / 100
    const l = parseFloat(parts[2]) / 100
    a = isHsla ? parseFloat(parts[3]) : 1
    ;[r, g, b] = hslToRgb(h, s, l)
  } else if (input.startsWith('#')) {
    const c = input.slice(1)
    if (c.length === 3) {
      r = parseInt(c[0] + c[0], 16) / 255
      g = parseInt(c[1] + c[1], 16) / 255
      b = parseInt(c[2] + c[2], 16) / 255
    } else if (c.length >= 6) {
      r = parseInt(c.slice(0, 2), 16) / 255
      g = parseInt(c.slice(2, 4), 16) / 255
      b = parseInt(c.slice(4, 6), 16) / 255
      if (c.length === 8) {
        a = parseInt(c.slice(6, 8), 16) / 255
      }
    }
  }

  return [r, g, b, a]
}

function hslToRgb(h: number, s: number, l: number): [number, number, number] {
  if (s === 0) {
    return [l, l, l]
  }

  const hue2rgb = (p: number, q: number, t: number) => {
    if (t < 0) t += 1
    if (t > 1) t -= 1
    if (t < 1 / 6) return p + (q - p) * 6 * t
    if (t < 1 / 2) return q
    if (t < 2 / 3) return p + (q - p) * (2 / 3 - t) * 6
    return p
  }

  const q = l < 0.5 ? l * (1 + s) : l + s - l * s
  const p = 2 * l - q
  return [
    hue2rgb(p, q, h + 1 / 3),
    hue2rgb(p, q, h),
    hue2rgb(p, q, h - 1 / 3),
  ]
}
</script>

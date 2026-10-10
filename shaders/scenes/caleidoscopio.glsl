// Escena caleidoscopio: nebulosa plegada en espejo que reacciona al audio.
// Entrada 0: el frame anterior de este mismo shader, para dejar estelas.

uniform vec4 uAudio; // low, mid, high, level en el rango 0-1
uniform vec4 uClock; // seconds, low_phase, mid_phase, sin uso
uniform vec4 uBeat;  // beat (1 en el golpe y se apaga), beat_count

out vec4 fragColor;

const float TAU = 6.28318530718;

// Los gajos del caleidoscopio cambian cada BEATS_PER_SHAPE golpes y recorren
// SEGMENTS_MIN, +2, +4 y vuelta a empezar.
const float SEGMENTS_MIN = 4.0;
const float BEATS_PER_SHAPE = 8.0;

// Cuánto se corre la paleta de color en cada golpe.
const float BEAT_HUE_STEP = 0.13;

// Estelas: cuánto sobrevive el frame anterior y cuánto se aleja del centro.
const float TRAIL_DECAY = 0.88;
const float TRAIL_ZOOM = 0.012;

mat2 rotate(float angle)
{
	float s = sin(angle);
	float c = cos(angle);
	return mat2(c, -s, s, c);
}

float hash21(vec2 p)
{
	p = fract(p * vec2(123.34, 456.21));
	p += dot(p, p + 45.32);
	return fract(p.x * p.y);
}

float valueNoise(vec2 p)
{
	vec2 cell = floor(p);
	vec2 local = fract(p);
	vec2 blend = local * local * (3.0 - 2.0 * local);
	float a = hash21(cell);
	float b = hash21(cell + vec2(1.0, 0.0));
	float c = hash21(cell + vec2(0.0, 1.0));
	float d = hash21(cell + vec2(1.0, 1.0));
	return mix(mix(a, b, blend.x), mix(c, d, blend.x), blend.y);
}

float fbm(vec2 p)
{
	float total = 0.0;
	float amplitude = 0.5;
	mat2 turn = rotate(0.5);
	for (int i = 0; i < 5; i++)
	{
		total += amplitude * valueNoise(p);
		p = turn * p * 2.0 + 17.0;
		amplitude *= 0.5;
	}
	return total;
}

// Paleta por cosenos: recorre magenta, azul, cian y naranja.
vec3 palette(float t)
{
	return 0.5 + 0.5 * cos(TAU * (t + vec3(0.0, 0.33, 0.67)));
}

// Pliega el plano en gajos iguales reflejados alrededor del centro.
vec2 kaleido(vec2 p, float segments)
{
	float slice = TAU / segments;
	float angle = mod(atan(p.y, p.x), slice);
	angle = abs(angle - 0.5 * slice);
	return length(p) * vec2(cos(angle), sin(angle));
}

void main()
{
	float low = uAudio.x;
	float mid = uAudio.y;
	float high = uAudio.z;
	float level = uAudio.w;
	float seconds = uClock.x;
	float lowPhase = uClock.y;
	float midPhase = uClock.z;
	float beat = uBeat.x;
	float beatCount = uBeat.y;

	// Arranca en seis gajos y cambia de forma cada pocos golpes.
	float shape = mod(floor(beatCount / BEATS_PER_SHAPE) + 1.0, 3.0);
	float segments = SEGMENTS_MIN + 2.0 * shape;
	float hue = BEAT_HUE_STEP * beatCount;

	vec2 resolution = uTDOutputInfo.res.zw;
	vec2 centered = vUV.st - 0.5;
	vec2 p = centered * vec2(resolution.x / resolution.y, 1.0);

	// Los graves acercan la imagen, cada golpe da un empujón y todo gira despacio.
	p *= 1.0 - 0.22 * low - 0.12 * beat;
	p = rotate(0.07 * seconds + 0.25 * midPhase) * p;
	float radius = length(p);
	vec2 folded = kaleido(p, segments);

	// Nebulosa: ruido deformado por más ruido; los medios aumentan la deformación.
	vec2 q = folded * 2.6 - vec2(lowPhase, 0.0);
	vec2 warp = vec2(fbm(q + 0.3 * midPhase), fbm(q + 5.2 - 0.3 * midPhase));
	float cloud = fbm(q + (1.2 + 2.2 * mid) * warp);
	vec3 color = palette(hue + cloud + 0.35 * radius + 0.04 * seconds + 0.25 * mid);
	color *= smoothstep(0.25, 0.8, cloud) * (0.3 + 1.1 * level + 0.6 * beat);

	// Anillos que salen del centro al ritmo de los graves.
	float rings = 0.5 + 0.5 * cos(TAU * (3.5 * radius - 1.5 * lowPhase));
	color += palette(hue + 0.5 + radius - 0.2 * lowPhase) * pow(rings, 8.0) * low;

	// Chispas que parpadean con los agudos.
	vec2 spark = floor(folded * 42.0);
	float flicker = hash21(spark + floor(12.0 * seconds));
	color += vec3(step(1.0 - 0.05 * high, flicker)) * high;

	// Núcleo que se enciende con los graves y destella en cada golpe.
	float core = 0.06 * low * low + 0.05 * beat;
	color += palette(hue + 0.05 * seconds) * core / (radius * radius + 0.02);

	color *= smoothstep(1.1, 0.25, radius);

	// Estelas: el frame anterior se aleja del centro y se apaga de a poco.
	vec2 trailUV = 0.5 + rotate(0.004) * centered * (1.0 - TRAIL_ZOOM - 0.03 * low);
	vec3 trail = texture(sTD2DInputs[0], trailUV).rgb * TRAIL_DECAY;
	color = max(color, trail);

	fragColor = TDOutputSwizzle(vec4(color, 1.0));
}

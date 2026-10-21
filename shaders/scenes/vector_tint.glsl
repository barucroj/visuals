// Tiñe las estelas grises del vectorscopio con la paleta acotada.
//
// La entrada trae la densidad de la nube en gris. El color recorre la
// paleta sin saltos, y lo más denso se aclara hacia su propio tono claro
// y destella en cada golpe.
//
// Uniforms:
//   uPhase.x  posición en la paleta (una vuelta por unidad)
//   uPhase.y  envolvente del golpe, 0 a 1

uniform vec2 uPhase;

out vec4 fragColor;

// Paleta: azules, verde apagado, gris, naranja y rojo. Del rojo se pasa a
// casi negro antes de volver al azul: mezclado con un gris o con el azul,
// el rojo da rosa o violeta.
const int PALETTE_SIZE = 7;
const vec3 PALETTE[PALETTE_SIZE] = vec3[PALETTE_SIZE](
	vec3(0.10, 0.30, 0.75), // azul
	vec3(0.20, 0.60, 0.80), // azul acero
	vec3(0.25, 0.55, 0.35), // verde apagado
	vec3(0.55, 0.58, 0.60), // gris
	vec3(0.95, 0.45, 0.12), // naranja
	vec3(0.85, 0.12, 0.08), // rojo
	vec3(0.10, 0.10, 0.12)  // carbón
);

// Color de lo más denso para cada color de la paleta. No se usa blanco:
// el rojo mezclado con blanco da rosa.
const vec3 HIGHLIGHTS[PALETTE_SIZE] = vec3[PALETTE_SIZE](
	vec3(0.75, 0.88, 1.00), // azul claro
	vec3(0.80, 0.95, 1.00), // azul acero claro
	vec3(0.70, 0.90, 0.72), // verde claro
	vec3(0.92, 0.94, 0.96), // blanco grisáceo
	vec3(1.00, 0.72, 0.38), // naranja claro
	vec3(1.00, 0.38, 0.12), // rojo anaranjado
	vec3(0.30, 0.30, 0.34)  // gris oscuro
);

vec3 pick(const vec3 colors[PALETTE_SIZE], float t)
{
	float x = fract(t) * float(PALETTE_SIZE);
	int i = int(x);
	float f = smoothstep(0.0, 1.0, fract(x));
	return mix(colors[i], colors[(i + 1) % PALETTE_SIZE], f);
}

void main()
{
	vec3 source = texture(sTD2DInputs[0], vUV.st).rgb;
	float density = max(max(source.r, source.g), source.b);

	vec3 color = pick(PALETTE, uPhase.x) * smoothstep(0.0, 0.6, density) * (1.4 + 0.6 * uPhase.y);
	color = mix(color, pick(HIGHLIGHTS, uPhase.x), smoothstep(0.75, 1.0, density) * (0.6 + 0.4 * uPhase.y));
	fragColor = TDOutputSwizzle(vec4(color, 1.0));
}

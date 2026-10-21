"""Arma la escena vector dentro del proyecto abierto.

Un vectorscopio dibuja cada píxel de su entrada según su tono y saturación.
La entrada pone lado a lado una foto multicolor, que da rayos hacia todos
lados en forma de estrella, y la salida del caleidoscopio, que da los hilos.
El brillo del caleidoscopio también enmascara la foto para que los rayos
crezcan y se encojan con él. El audio alarga los rayos, mueve el giro, la
escala y las estelas, y hace avanzar el color por la paleta. Necesita la
red de audio y la escena caleidoscopio. Uso, en el Textport (Alt+T):

exec(open(project.folder + '/../scripts/build/build_vector.py', encoding='utf-8').read(), globals())

Se puede volver a ejecutar: reemplaza la escena anterior.
"""

import os

CLOCK_FILE = '../scripts/audio/audio_clock.py'
WANDER_FILE = '../scripts/audio/audio_wander.py'
SHADER_FILE = '../shaders/scenes/vector_tint.glsl'
AUDIO_NAME = 'audio'
SOURCE_SCENE = 'caleidoscopio'
SCENE_NAME = 'vector'
VIEW_NAME = 'vector_view'
RESOLUTION = (1280, 720)
PIXEL_FORMAT = 'rgba16float'

# El vectorscopio es un componente de la Palette; se carga desde la
# instalación de TouchDesigner en vez de copiarlo al repo.
SCOPE_TOX = 'Samples/Palette/Tools/vectorScope.tox'

# Foto de gomitas de muchos colores, de los ejemplos de TouchDesigner: da
# un rayo por cada tono. Es la misma que usa el ejemplo del vectorscopio.
SOURCE_IMAGE = 'Map/Jellybeans.1.jpg'

# Cada píxel de la imagen analizada es un punto: a menor resolución,
# menos puntos y menos costo.
SOURCE_RESOLUTION = (640, 360)

# En el vectorscopio el tono de un píxel es su ángulo, así que girar el
# tono de un grupo de píxeles gira sus brazos. La foto se parte en tercios
# y cada tercio, igual que el caleidoscopio, gira con el ángulo errante de
# una banda.
IMAGE_BANDS = ('low_angle', 'mid_angle', 'high_angle')
KALEIDO_BAND = 'level_angle'

# Cuadrícula de 2 x 2 con los cuatro grupos que entra al vectorscopio.
LAYOUT_RESOLUTION = (1280, 480)

# Degradado que marca la densidad de la nube, en gris: el color se pone
# después, fuera del lazo de estelas. Cada fila es pos, r, g, b, a.
RAMP_KEYS = (
	(0.0, 0.0, 0.0, 0.0, 1.0),
	(0.378, 0.3, 0.3, 0.3, 1.0),
	(0.872, 0.8, 0.8, 0.8, 1.0),
	(1.0, 1.0, 1.0, 1.0, 1.0),
)

# Vueltas por segundo a la paleta: una base constante y lo que suma el reloj
# de graves, que corre más rápido cuanto más fuertes suenan.
PALETTE_SPEED = 0.025
PALETTE_LOW_SPEED = 0.06


def _warn(message):
	print('[build_vector] ' + message)


def _par(target, name):
	par = getattr(target.par, name, None)
	if par is None:
		_warn('parametro no encontrado: {}.{}'.format(target.name, name))
	return par


def _set(target, name, value):
	par = _par(target, name)
	if par is not None:
		par.val = value


def _expr(target, name, expression):
	par = _par(target, name)
	if par is not None:
		par.expr = expression
		par.mode = ParMode.EXPRESSION


def _replace(container, op_type, name):
	old = container.op(name)
	if old is not None:
		old.destroy()
	return container.create(op_type, name)


def _file_dat(container, name, path):
	"""Crea un Text DAT con el contenido de un archivo del repo, sin Sync to File."""
	dat = container.create(textDAT, name)
	with open(project.folder + '/' + path, encoding='utf-8-sig') as source:
		dat.text = source.read()
	return dat


def _resolution(top, size=RESOLUTION):
	_set(top, 'outputresolution', 'custom')
	_set(top, 'resolutionw', size[0])
	_set(top, 'resolutionh', size[1])
	_set(top, 'format', PIXEL_FORMAT)


def _uniform(glsl, index, name, expressions):
	prefix = 'vec{}'.format(index)
	_set(glsl, prefix + 'name', name)
	for axis, expression in zip('xyzw', expressions):
		_expr(glsl, prefix + 'value' + axis, expression)


def _build_clock(scene):
	audio_in = scene.create(selectCHOP, 'audio_in')
	audio_in.nodeX, audio_in.nodeY = 0, 0
	_set(audio_in, 'chops', '../{}/out1'.format(AUDIO_NAME))

	code = _file_dat(scene, 'clock_code', CLOCK_FILE)
	code.nodeX, code.nodeY = 200, -150

	clock = scene.create(scriptCHOP, 'clock')
	clock.nodeX, clock.nodeY = 200, 0
	for docked in list(clock.docked):
		docked.destroy()
	_set(clock, 'callbacks', code.name)
	clock.inputConnectors[0].connect(audio_in)

	wander_code = _file_dat(scene, 'wander_code', WANDER_FILE)
	wander_code.nodeX, wander_code.nodeY = 400, -150

	wander = scene.create(scriptCHOP, 'wander')
	wander.nodeX, wander.nodeY = 400, 0
	for docked in list(wander.docked):
		docked.destroy()
	_set(wander, 'callbacks', wander_code.name)
	wander.inputConnectors[0].connect(audio_in)
	return audio_in, clock, wander


def _hue(scene, name, source, angle, position):
	hue = scene.create(hsvadjustTOP, name)
	hue.nodeX, hue.nodeY = position
	hue.inputConnectors[0].connect(source)
	_expr(hue, 'hueoffset', angle)
	return hue


def _build_source(scene, audio, wander_value):
	image = scene.create(moviefileinTOP, 'image')
	image.nodeX, image.nodeY = -1400, -300
	_expr(image, 'file', "app.samplesFolder + '/{}'".format(SOURCE_IMAGE))
	_resolution(image, SOURCE_RESOLUTION)

	# Más saturación aleja los puntos del centro: los rayos crecen con los
	# graves y saltan en cada golpe.
	pulse = scene.create(hsvadjustTOP, 'pulse')
	pulse.nodeX, pulse.nodeY = -1200, -300
	pulse.inputConnectors[0].connect(image)
	_expr(pulse, 'saturationmult', '1.0 + 0.8 * {} + 0.4 * {}'.format(
		audio.format('low'), audio.format('beat')))

	kaleido = scene.create(selectTOP, 'kaleido')
	kaleido.nodeX, kaleido.nodeY = -1400, -150
	_set(kaleido, 'top', '../{}/out1'.format(SOURCE_SCENE))
	_resolution(kaleido, SOURCE_RESOLUTION)

	# Máscara gris para no teñir la foto. Un piso evita que la estrella se
	# junte en el centro cuando el caleidoscopio se oscurece.
	mono = scene.create(monochromeTOP, 'mono')
	mono.nodeX, mono.nodeY = -1200, -150
	mono.inputConnectors[0].connect(kaleido)
	boost = scene.create(levelTOP, 'boost')
	boost.nodeX, boost.nodeY = -1000, -150
	boost.inputConnectors[0].connect(mono)
	_set(boost, 'brightness1', 1.6)
	_set(boost, 'outlow', 0.5)

	mask = scene.create(compositeTOP, 'mask')
	mask.nodeX, mask.nodeY = -1000, -300
	mask.inputConnectors[0].connect(pulse)
	mask.inputConnectors[1].connect(boost)
	_set(mask, 'operand', 'multiply')

	parts = []
	count = len(IMAGE_BANDS)
	for index, band in enumerate(IMAGE_BANDS):
		crop = scene.create(cropTOP, 'crop{}'.format(index + 1))
		crop.nodeX, crop.nodeY = -800, -300 - 150 * index
		crop.inputConnectors[0].connect(mask)
		_set(crop, 'cropleft', index / count)
		_set(crop, 'cropright', (index + 1) / count)
		parts.append(_hue(scene, 'hue{}'.format(index + 1), crop,
			wander_value.format(band), (-600, -300 - 150 * index)))
	parts.append(_hue(scene, 'hue_kaleido', kaleido,
		wander_value.format(KALEIDO_BAND), (-600, -150)))

	# El vectorscopio no mira dónde está cada píxel, así que las imágenes
	# se acomodan en una cuadrícula en vez de sumarse: sumadas, sus colores
	# se mezclarían y la nube se juntaría en el centro. Cada celda tiene el
	# mismo tamaño para que cada grupo aporte los mismos puntos.
	source = scene.create(layoutTOP, 'source')
	source.nodeX, source.nodeY = -200, -300
	for index, part in enumerate(parts):
		source.inputConnectors[index].connect(part)
	_set(source, 'align', 'gridrows')
	_set(source, 'maxcols', 2)
	_set(source, 'fit', 'fill')
	_resolution(source, LAYOUT_RESOLUTION)
	return source


def _build_scope(scene, source, audio):

	# El .tox de la Palette envuelve el vectorscopio en un Base COMP con su
	# ícono; se copia el componente de adentro y se descarta el envoltorio.
	wrapper = scene.loadTox(app.installFolder + '/' + SCOPE_TOX)
	scope = scene.copy(wrapper.op('vectorScope'), name='scope')
	wrapper.destroy()
	scope.nodeX, scope.nodeY = 200, -300
	scope.inputConnectors[0].connect(source)
	_set(scope, 'Resolutionw', RESOLUTION[0])
	_set(scope, 'Resolutionh', RESOLUTION[1])
	_set(scope, 'Targetlevel', 0.567)
	_set(scope, 'Huedelta', 0.0368)
	_set(scope, 'Satdelta', 0.1812)
	# La retícula queda tenue y fija para que no domine sobre la estrella.
	# El vectorScope 2 de TouchDesigner 2025 ya no dibuja retícula ni tiene
	# este parámetro.
	if hasattr(scope.par, 'Displaybrightness'):
		_set(scope, 'Displaybrightness', 0.414)
	# Los puntos se ven más con el volumen.
	_expr(scope, 'Outputgain', '0.08 + 0.12 * {}'.format(audio.format('level')))
	return scope


def _build_motion(scene, scope, audio, clock_value):
	# Gira más rápido con los medios, crece con los graves y salta en cada golpe.
	transform = scene.create(transformTOP, 'transform')
	transform.nodeX, transform.nodeY = 400, -300
	transform.inputConnectors[0].connect(scope.outputConnectors[0])
	_expr(transform, 'rotate', '-(25 * {} + 30 * {})'.format(
		clock_value.format('seconds'), clock_value.format('mid_phase')))
	scale = '2.4 * (1 + 0.2 * {} + 0.1 * {})'.format(audio.format('low'), audio.format('beat'))
	_expr(transform, 'sx', scale)
	_expr(transform, 'sy', scale)

	black = scene.create(constantTOP, 'black')
	black.nodeX, black.nodeY = 400, -450
	for channel in ('colorr', 'colorg', 'colorb'):
		_set(black, channel, 0)
	_resolution(black)

	over = scene.create(overTOP, 'over')
	over.nodeX, over.nodeY = 600, -300
	over.inputConnectors[0].connect(transform)
	over.inputConnectors[1].connect(black)
	return over


def _build_density(scene, over):
	ramp = scene.create(rampTOP, 'ramp')
	ramp.nodeX, ramp.nodeY = 600, -450
	# El Ramp TOP trae su tabla de colores acoplada; si no, se crea una.
	keys = ramp.par.dat.eval() or scene.create(tableDAT, 'ramp_keys')
	keys.clear()
	keys.appendRow(['pos', 'r', 'g', 'b', 'a'])
	for row in RAMP_KEYS:
		keys.appendRow(list(row))
	_set(ramp, 'dat', keys.name)

	lookup = scene.create(lookupTOP, 'lookup')
	lookup.nodeX, lookup.nodeY = 800, -300
	lookup.inputConnectors[0].connect(over)
	lookup.inputConnectors[1].connect(ramp)
	_set(lookup, 'channel', 'red')
	return lookup


def _build_trails(scene, density, audio):
	feedback = scene.create(feedbackTOP, 'feedback')
	feedback.nodeX, feedback.nodeY = 1200, -450
	feedback.inputConnectors[0].connect(density)

	comp = scene.create(compositeTOP, 'comp')
	comp.nodeX, comp.nodeY = 1200, -300
	comp.inputConnectors[0].connect(feedback)
	comp.inputConnectors[1].connect(density)
	_set(comp, 'operand', 'screen')
	_resolution(comp)

	# Las estelas duran más cuando sube el volumen.
	fade = scene.create(levelTOP, 'fade')
	fade.nodeX, fade.nodeY = 1400, -300
	fade.inputConnectors[0].connect(comp)
	_set(fade, 'inlow', 0.022)
	_expr(fade, 'opacity', '0.86 + 0.08 * {}'.format(audio.format('level')))
	_set(feedback, 'top', fade.name)
	return fade


def _build_tint(scene, trails, audio, clock_value):
	# El color se pone fuera del lazo de estelas: así las estelas viejas
	# cambian de tono junto con la nueva y no se mezclan en otros colores.
	code = _file_dat(scene, 'tint_code', SHADER_FILE)
	code.nodeX, code.nodeY = 1600, -450

	tint = scene.create(glslTOP, 'tint')
	tint.nodeX, tint.nodeY = 1600, -300
	for docked in list(tint.docked):
		docked.destroy()
	_set(tint, 'pixeldat', code.name)
	_resolution(tint)
	tint.inputConnectors[0].connect(trails)
	phase = '{} * {} + {} * {}'.format(
		PALETTE_SPEED, clock_value.format('seconds'),
		PALETTE_LOW_SPEED, clock_value.format('low_phase'))
	_uniform(tint, 0, 'uPhase', [phase, audio.format('beat')])

	out = scene.create(outTOP, 'out1')
	out.nodeX, out.nodeY = 1800, -300
	out.inputConnectors[0].connect(tint)
	out.viewer = True
	return out


def build():
	container = op('/project1') or op('/')
	if container.op(AUDIO_NAME) is None:
		_warn('falta la red de audio; ejecuta primero build_audio.py')
		return
	if container.op(SOURCE_SCENE) is None:
		_warn('falta la escena caleidoscopio; ejecuta primero build_caleidoscopio.py')
		return
	if not os.path.isfile(app.installFolder + '/' + SCOPE_TOX):
		_warn('no se encontro {} en la instalacion de TouchDesigner'.format(SCOPE_TOX))
		return
	if not os.path.isfile(app.samplesFolder + '/' + SOURCE_IMAGE):
		_warn('no se encontro {} en los ejemplos de TouchDesigner'.format(SOURCE_IMAGE))
		return

	scene = _replace(container, baseCOMP, SCENE_NAME)
	scene.nodeX, scene.nodeY = 0, -800
	audio_in, clock, wander = _build_clock(scene)
	# Rutas completas: algunas expresiones viven dentro del vectorscopio,
	# donde un nombre relativo no encuentra los canales.
	audio = "op('{}')['{{}}']".format(audio_in.path)
	clock_value = "op('{}')['{{}}']".format(clock.path)
	wander_value = "op('{}')['{{}}']".format(wander.path)
	source = _build_source(scene, audio, wander_value)
	scope = _build_scope(scene, source, audio)
	over = _build_motion(scene, scope, audio, clock_value)
	density = _build_density(scene, over)
	trails = _build_trails(scene, density, audio)
	out = _build_tint(scene, trails, audio, clock_value)

	# Vista de la escena al nivel del proyecto.
	view = _replace(container, selectTOP, VIEW_NAME)
	view.nodeX, view.nodeY = 250, -800
	_set(view, 'top', '{}/{}'.format(scene.name, out.name))
	view.viewer = True
	_warn('listo: {} y {}'.format(scene.path, view.path))


build()

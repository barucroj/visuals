"""Arma la escena vector dentro del proyecto abierto.

Un vectorscopio dibuja cada píxel de la salida del caleidoscopio según su
tono y saturación, y el audio mueve el giro, la escala, el color y las
estelas. Necesita la red de audio y la escena caleidoscopio. Uso, en el
Textport (Alt+T):

exec(open(project.folder + '/../scripts/build/build_vector.py', encoding='utf-8').read(), globals())

Se puede volver a ejecutar: reemplaza la escena anterior.
"""

import os

CLOCK_FILE = '../scripts/audio/audio_clock.py'
AUDIO_NAME = 'audio'
SOURCE_SCENE = 'caleidoscopio'
SCENE_NAME = 'vector'
VIEW_NAME = 'vector_view'
RESOLUTION = (1280, 720)
PIXEL_FORMAT = 'rgba16float'

# El vectorscopio es un componente de la Palette; se carga desde la
# instalación de TouchDesigner en vez de copiarlo al repo.
SCOPE_TOX = 'Samples/Palette/Tools/vectorScope.tox'

# Cada píxel de la imagen analizada es un punto: a menor resolución,
# menos puntos y menos costo.
SOURCE_RESOLUTION = (640, 360)

# Degradado que colorea la nube según su densidad: negro, violeta,
# magenta y blanco. Cada fila es pos, r, g, b, a.
RAMP_KEYS = (
	(0.0, 0.0, 0.0, 0.0, 1.0),
	(0.378, 0.131, 0.455, 0.703, 1.0),
	(0.872, 0.161, 0.861, 0.383, 1.0),
	(1.0, 1.0, 1.0, 1.0, 1.0),
)

# Cuántos grados se corre el color en cada golpe.
BEAT_HUE_STEP = 47.0


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
	return audio_in, clock


def _build_scope(scene, audio):
	source = scene.create(selectTOP, 'source')
	source.nodeX, source.nodeY = 0, -300
	_set(source, 'top', '../{}/out1'.format(SOURCE_SCENE))
	_resolution(source, SOURCE_RESOLUTION)

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
	# Los puntos se ven más con el volumen y la imagen brilla con los agudos.
	_expr(scope, 'Outputgain', '0.08 + 0.12 * {}'.format(audio.format('level')))
	_expr(scope, 'Displaybrightness', '0.35 + 0.4 * {}'.format(audio.format('high')))
	return scope


def _build_motion(scene, scope, audio, clock_value):
	# Gira más rápido con los medios, crece con los graves y salta en cada golpe.
	transform = scene.create(transformTOP, 'transform')
	transform.nodeX, transform.nodeY = 400, -300
	transform.inputConnectors[0].connect(scope.outputConnectors[0])
	_expr(transform, 'rotate', '-(15 * {} + 40 * {})'.format(
		clock_value.format('seconds'), clock_value.format('mid_phase')))
	scale = '2 * (1 + 0.25 * {} + 0.15 * {})'.format(audio.format('low'), audio.format('beat'))
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


def _build_color(scene, over, audio):
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

	hue = scene.create(hsvadjustTOP, 'hue')
	hue.nodeX, hue.nodeY = 1000, -300
	hue.inputConnectors[0].connect(lookup)
	_expr(hue, 'hueoffset', '({} * {}) % 360'.format(BEAT_HUE_STEP, audio.format('beat_count')))
	return hue


def _build_trails(scene, color, audio):
	feedback = scene.create(feedbackTOP, 'feedback')
	feedback.nodeX, feedback.nodeY = 1200, -450
	feedback.inputConnectors[0].connect(color)

	comp = scene.create(compositeTOP, 'comp')
	comp.nodeX, comp.nodeY = 1200, -300
	comp.inputConnectors[0].connect(feedback)
	comp.inputConnectors[1].connect(color)
	_set(comp, 'operand', 'screen')
	_resolution(comp)

	# Las estelas duran más cuando sube el volumen.
	fade = scene.create(levelTOP, 'fade')
	fade.nodeX, fade.nodeY = 1400, -300
	fade.inputConnectors[0].connect(comp)
	_set(fade, 'inlow', 0.022)
	_expr(fade, 'opacity', '0.86 + 0.08 * {}'.format(audio.format('level')))
	_set(feedback, 'top', fade.name)

	out = scene.create(outTOP, 'out1')
	out.nodeX, out.nodeY = 1600, -300
	out.inputConnectors[0].connect(fade)
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

	scene = _replace(container, baseCOMP, SCENE_NAME)
	scene.nodeX, scene.nodeY = 0, -800
	audio_in, clock = _build_clock(scene)
	# Rutas completas: algunas expresiones viven dentro del vectorscopio,
	# donde un nombre relativo no encuentra los canales.
	audio = "op('{}')['{{}}']".format(audio_in.path)
	clock_value = "op('{}')['{{}}']".format(clock.path)
	scope = _build_scope(scene, audio)
	over = _build_motion(scene, scope, audio, clock_value)
	color = _build_color(scene, over, audio)
	out = _build_trails(scene, color, audio)

	# Vista de la escena al nivel del proyecto.
	view = _replace(container, selectTOP, VIEW_NAME)
	view.nodeX, view.nodeY = 250, -800
	_set(view, 'top', '{}/{}'.format(scene.name, out.name))
	view.viewer = True
	_warn('listo: {} y {}'.format(scene.path, view.path))


build()

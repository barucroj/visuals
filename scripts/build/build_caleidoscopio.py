"""Arma la escena caleidoscopio dentro del proyecto abierto.

Necesita la red de audio de build_audio.py. Uso, en el Textport (Alt+T):

exec(open(project.folder + '/../scripts/build/build_caleidoscopio.py', encoding='utf-8').read(), globals())

Se puede volver a ejecutar: reemplaza la escena anterior.
"""

import td

SHADER_FILE = '../shaders/scenes/caleidoscopio.glsl'
CLOCK_FILE = '../scripts/audio/audio_clock.py'
AUDIO_NAME = 'audio'
SCENE_NAME = 'caleidoscopio'
VIEW_NAME = 'caleidoscopio_view'
RESOLUTION = (1280, 720)

# Formato de 16 bits para que las estelas se apaguen sin dejar residuo.
PIXEL_FORMAT = 'rgba16float'


def _warn(message):
	print('[build_caleidoscopio] ' + message)


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
	"""Crea un Text DAT que refleja un archivo del repo."""
	dat = container.create(textDAT, name)
	_set(dat, 'file', path)
	_set(dat, 'syncfile', True)
	if not dat.text:
		with open(project.folder + '/' + path, encoding='utf-8-sig') as source:
			dat.text = source.read()
	return dat


def _resolution(top):
	_set(top, 'outputresolution', 'custom')
	_set(top, 'resolutionw', RESOLUTION[0])
	_set(top, 'resolutionh', RESOLUTION[1])
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
	return audio_in, clock


def _build_shader(scene, audio_in, clock):
	code = _file_dat(scene, 'shader_code', SHADER_FILE)
	code.nodeX, code.nodeY = 400, -450

	black = scene.create(constantTOP, 'black')
	black.nodeX, black.nodeY = 0, -300
	for channel in ('colorr', 'colorg', 'colorb'):
		_set(black, channel, 0)
	_resolution(black)

	feedback = scene.create(feedbackTOP, 'feedback')
	feedback.nodeX, feedback.nodeY = 200, -300
	feedback.inputConnectors[0].connect(black)

	shader = scene.create(glslTOP, 'shader')
	shader.nodeX, shader.nodeY = 400, -300
	for docked in list(shader.docked):
		docked.destroy()
	_set(shader, 'pixeldat', code.name)
	_resolution(shader)
	shader.inputConnectors[0].connect(feedback)
	_set(feedback, 'top', shader.name)

	try:
		shader.par.vec0name.sequence.numBlocks = 3
	except Exception as error:
		_warn('no se pudieron agregar los uniforms: {}'.format(error))
	audio = "op('{}')['{{}}']".format(audio_in.name)
	_uniform(shader, 0, 'uAudio', [audio.format(name) for name in ('low', 'mid', 'high', 'level')])
	clock_value = "op('{}')['{{}}']".format(clock.name)
	_uniform(shader, 1, 'uClock', [clock_value.format(name) for name in ('seconds', 'low_phase', 'mid_phase')])
	_uniform(shader, 2, 'uBeat', [audio.format(name) for name in ('beat', 'beat_count')])
	return shader


def _build_output(scene, shader):
	last = shader
	bloom_type = getattr(td, 'bloomTOP', None)
	if bloom_type is None:
		_warn('esta version no tiene Bloom TOP; la escena sale sin resplandor')
	else:
		bloom = scene.create(bloom_type, 'bloom')
		bloom.nodeX, bloom.nodeY = 600, -300
		bloom.inputConnectors[0].connect(shader)
		last = bloom

	out = scene.create(outTOP, 'out1')
	out.nodeX, out.nodeY = 800, -300
	out.inputConnectors[0].connect(last)
	out.viewer = True
	return out


def build():
	container = op('/project1') or op('/')
	if container.op(AUDIO_NAME) is None:
		_warn('falta la red de audio; ejecuta primero build_audio.py')
		return

	scene = _replace(container, baseCOMP, SCENE_NAME)
	scene.nodeX, scene.nodeY = 0, -600
	audio_in, clock = _build_clock(scene)
	shader = _build_shader(scene, audio_in, clock)
	out = _build_output(scene, shader)

	# Vista de la escena al nivel del proyecto.
	view = _replace(container, selectTOP, VIEW_NAME)
	view.nodeX, view.nodeY = 250, -600
	_set(view, 'top', '{}/{}'.format(scene.name, out.name))
	view.viewer = True
	_warn('listo: {} y {}'.format(scene.path, view.path))


build()

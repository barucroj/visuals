"""Arma la red de análisis de audio dentro del proyecto abierto.

Uso: guardar el .toe en la carpeta project/ y ejecutar en el Textport (Alt+T):

exec(open(project.folder + '/../scripts/build/build_audio.py', encoding='utf-8').read(), globals())

Se puede volver a ejecutar: reemplaza la red anterior.
"""

ANALYSIS_FILE = '../scripts/audio/audio_analysis.py'
AUDIO_NAME = 'audio'
PREVIEW_NAME = 'audio_preview'


def _warn(message):
	print('[build_audio] ' + message)


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


def _build_audio(container):
	audio = _replace(container, baseCOMP, AUDIO_NAME)

	device = audio.create(audiodeviceinCHOP, 'in_device')
	device.nodeX, device.nodeY = 0, 0

	# El código vive en el repo; el DAT guarda una copia. No usa Sync to
	# File: con esa opción TouchDesigner escribe de vuelta y pisa el archivo
	# del repo (la versión 2025 le agrega un BOM al inicio).
	code = audio.create(textDAT, 'analysis_code')
	code.nodeX, code.nodeY = 200, -150
	with open(project.folder + '/' + ANALYSIS_FILE, encoding='utf-8-sig') as source:
		code.text = source.read()

	analysis = audio.create(scriptCHOP, 'analysis')
	analysis.nodeX, analysis.nodeY = 200, 0
	for docked in list(analysis.docked):
		docked.destroy()
	_set(analysis, 'callbacks', code.name)
	analysis.inputConnectors[0].connect(device)

	out = audio.create(outCHOP, 'out1')
	out.nodeX, out.nodeY = 400, 0
	out.inputConnectors[0].connect(analysis)
	out.viewer = True
	return audio


def _build_preview(container):
	"""Círculo de prueba: el radio sigue a los graves y el color a medios y agudos."""
	preview = _replace(container, circleTOP, PREVIEW_NAME)
	source = "op('{}/out1')".format(AUDIO_NAME)
	radius = "0.08 + 0.38 * {}['low']".format(source)
	_expr(preview, 'radiusx', radius)
	_expr(preview, 'radiusy', radius)
	_expr(preview, 'fillcolorr', "0.2 + 0.8 * {}['high']".format(source))
	_expr(preview, 'fillcolorg', "0.2 + 0.8 * {}['mid']".format(source))
	_expr(preview, 'fillcolorb', "1.0 - 0.6 * {}['level']".format(source))
	preview.viewer = True
	return preview


def build():
	container = op('/project1') or op('/')
	audio = _build_audio(container)
	audio.nodeX, audio.nodeY = 0, -400
	preview = _build_preview(container)
	preview.nodeX, preview.nodeY = 250, -400
	_warn('listo: {} y {}'.format(audio.path, preview.path))


build()

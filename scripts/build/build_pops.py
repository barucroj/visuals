"""Arma la escena pops dentro del proyecto abierto.

Una nube de partículas que vive en la GPU con POPs (Point Operators, nuevos
en TouchDesigner 2025). Las partículas no mueren: una fuerza las jala al
centro, un ruido curl las arrastra en remolinos y un giro las hace orbitar.
Cada partícula deja una estela corta, que se dibuja como un hilo. El audio
afloja el jalón con los graves, hace estallar la nube en cada golpe, tuerce
el giro con los medios y agita el ruido con los agudos. El color se pone al
final con la misma paleta de la escena vector. Necesita la red de audio y
TouchDesigner 2025 o más nuevo. Uso, en el Textport (Alt+T):

exec(open(project.folder + '/../scripts/build/build_pops.py', encoding='utf-8').read(), globals())

Se puede volver a ejecutar: reemplaza la escena anterior.
"""

import td

CLOCK_FILE = '../scripts/audio/audio_clock.py'
WANDER_FILE = '../scripts/audio/audio_wander.py'
SHADER_FILE = '../shaders/scenes/vector_tint.glsl'
AUDIO_NAME = 'audio'
SCENE_NAME = 'pops'
VIEW_NAME = 'pops_view'
RESOLUTION = (1280, 720)
PIXEL_FORMAT = 'rgba16float'

# Partículas en la nube. Ninguna muere, así que la estela nunca une la
# posición de una partícula vieja con la de una recién nacida, que cruzaría
# la imagen con una línea recta.
PARTICLES = 30000
EMITTER_RADIUS = 1.5
LIFE = 100000

# Frenado del aire: sin él las partículas se aceleran y salen de cuadro.
DRAG = 3.0

# Jalón hacia el centro (negativo) en silencio, cuánto lo aflojan los graves
# y empujón hacia afuera de cada golpe.
PULL = -2.5
PULL_LOW = 1.5
BEAT_PUSH = 9.0

# Fuerza del giro alrededor del eje y lo que suman los medios.
SPIRAL = 0.6
SPIRAL_MID = 2.0

# Ruido curl: tamaño de los remolinos, fuerza en silencio y lo que suman
# los agudos. La velocidad a la que cambia el campo sigue al reloj de medios.
NOISE_PERIOD = 1.5
NOISE_AMP = 3.0
NOISE_HIGH = 4.0
NOISE_SPEED = 0.12
NOISE_MID_SPEED = 0.15

# Largo de cada hilo en segundos, y lo que crece con el volumen.
TRAIL = 0.2
TRAIL_LEVEL = 0.2

# Gris de los hilos. Se suman entre sí, así que lo denso brilla más; el
# color se pone después con la paleta.
LINE_GRAY = 0.22

# Vueltas por segundo a la paleta, igual que en la escena vector.
PALETTE_SPEED = 0.025
PALETTE_LOW_SPEED = 0.06


def _warn(message):
	print('[build_pops] ' + message)


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


def _script_chop(scene, name, path, source, position):
	code = _file_dat(scene, name + '_code', path)
	code.nodeX, code.nodeY = position[0], position[1] - 150

	chop = scene.create(scriptCHOP, name)
	chop.nodeX, chop.nodeY = position
	for docked in list(chop.docked):
		docked.destroy()
	_set(chop, 'callbacks', code.name)
	chop.inputConnectors[0].connect(source)
	return chop


def _build_clock(scene):
	audio_in = scene.create(selectCHOP, 'audio_in')
	audio_in.nodeX, audio_in.nodeY = 0, 0
	_set(audio_in, 'chops', '../{}/out1'.format(AUDIO_NAME))
	clock = _script_chop(scene, 'clock', CLOCK_FILE, audio_in, (200, 0))
	wander = _script_chop(scene, 'wander', WANDER_FILE, audio_in, (400, 0))
	return audio_in, clock, wander


def _build_sim(scene, audio, clock_value, wander_value):
	emitter = scene.create(spherePOP, 'emitter')
	emitter.nodeX, emitter.nodeY = -600, -300
	_set(emitter, 'type', 'polar')
	for axis in ('radx', 'rady', 'radz'):
		_set(emitter, axis, EMITTER_RADIUS)

	# Nacen todas casi de una vez y después solo se mueven.
	particle = scene.create(particlePOP, 'particle')
	particle.nodeX, particle.nodeY = -400, -300
	particle.inputConnectors[0].connect(emitter)
	_set(particle, 'maxparticles', PARTICLES)
	_set(particle, 'birthrate', PARTICLES * 2)
	_set(particle, 'life', LIFE)
	_set(particle, 'initdrag', DRAG)

	# Jalón al centro y giro. El eje del giro se inclina con el ángulo
	# errante de los medios, así la órbita cambia de plano poco a poco.
	force = scene.create(forceradialPOP, 'force')
	force.nodeX, force.nodeY = -200, -300
	force.inputConnectors[0].connect(particle)
	_set(force, 'falloff', 'none')
	_expr(force, 'radialstrength', '{} + {} * {} + {} * {}'.format(
		PULL, PULL_LOW, audio.format('low'), BEAT_PUSH, audio.format('beat')))
	_set(force, 'spiral', True)
	angle = 'math.radians({})'.format(wander_value.format('mid_angle'))
	_expr(force, 'spiralrx', 'math.sin({})'.format(angle))
	_expr(force, 'spiralry', 'math.cos({})'.format(angle))
	_set(force, 'spiralrz', 0)
	_expr(force, 'spiralstrength', '{} + {} * {}'.format(
		SPIRAL, SPIRAL_MID, audio.format('mid')))
	_set(force, 'globforcemult', 0)

	# El curl de un ruido no tiene fuentes ni sumideros: arrastra las
	# partículas en remolinos sin juntarlas en un punto.
	noise = scene.create(noisePOP, 'noise')
	noise.nodeX, noise.nodeY = 0, -300
	noise.inputConnectors[0].connect(force)
	_set(noise, 'curl3d', True)
	_set(noise, 'combineentity', 'curl3d')
	_set(noise, 'combineattrscope', 'PartForce')
	_set(noise, 'combineop', 'add')
	_set(noise, 'period', NOISE_PERIOD)
	_expr(noise, 'amp0', '{} + {} * {}'.format(NOISE_AMP, NOISE_HIGH, audio.format('high')))
	_expr(noise, 't4d', '{} * {} + {} * {}'.format(
		NOISE_SPEED, clock_value.format('seconds'),
		NOISE_MID_SPEED, clock_value.format('mid_phase')))

	# El Particle POP toma este nodo como el final de su lazo y lo vuelve a
	# leer en el frame siguiente.
	sim = scene.create(nullPOP, 'sim')
	sim.nodeX, sim.nodeY = 200, -300
	sim.inputConnectors[0].connect(noise)
	_set(particle, 'targetpop', sim.name)

	trail = scene.create(trailPOP, 'trail')
	trail.nodeX, trail.nodeY = 400, -300
	trail.inputConnectors[0].connect(sim)
	_set(trail, 'lengthunit', 'seconds')
	_expr(trail, 'length', '{} + {} * {}'.format(TRAIL, TRAIL_LEVEL, audio.format('level')))
	_set(trail, 'fillmissedframes', True)
	return trail


def _build_render(scene, trail, audio, wander_value):
	# Los hilos se suman al dibujarse: donde se cruzan muchos, brilla más.
	line = scene.create(lineMAT, 'line')
	line.nodeX, line.nodeY = 600, -450
	_expr(line, 'widthnear', '1.2 + 1.5 * {}'.format(audio.format('beat')))
	_set(line, 'widthfar', 0.8)
	_set(line, 'linecoloratt', '')
	for prefix in ('linenear', 'linefar'):
		gray = LINE_GRAY if prefix == 'linenear' else LINE_GRAY * 0.5
		for channel in 'rgb':
			_set(line, '{}color{}'.format(prefix, channel), gray)
	_set(line, 'blending', True)
	_set(line, 'srcblend', 'one')
	_set(line, 'destblend', 'one')

	# Los POPs entran a la Geometry COMP por su conector, como en los
	# ejemplos de Derivative: adentro un In POP pasa directo al Out POP.
	geo = scene.create(geometryCOMP, 'geo')
	geo.nodeX, geo.nodeY = 600, -300
	for child in list(geo.children):
		child.destroy()
	geo_in = geo.create(inPOP, 'in1')
	geo_out = geo.create(outPOP, 'out1')
	geo_out.inputConnectors[0].connect(geo_in)
	geo_out.render = True
	geo_out.display = True
	geo.inputConnectors[0].connect(trail)
	_set(geo, 'material', line.name)
	# La nube se ve girar despacio desde ángulos que cambian con el volumen.
	_expr(geo, 'ry', wander_value.format('level_angle'))
	_expr(geo, 'rx', '20 * math.sin(math.radians({}))'.format(wander_value.format('low_angle')))

	camera = scene.create(cameraCOMP, 'camera')
	camera.nodeX, camera.nodeY = 600, -150
	_set(camera, 'tz', 7)

	render = scene.create(renderTOP, 'render')
	render.nodeX, render.nodeY = 800, -300
	_set(render, 'camera', camera.name)
	_set(render, 'geometry', geo.name)
	_set(render, 'lights', '')
	_set(render, 'bgcolora', 1)
	_resolution(render)
	return render


def _build_trails(scene, render, audio):
	# Estelas de imagen encima de las de los POPs: suavizan el parpadeo de
	# los hilos y dejan un rastro largo cuando la nube estalla.
	feedback = scene.create(feedbackTOP, 'feedback')
	feedback.nodeX, feedback.nodeY = 1000, -450
	feedback.inputConnectors[0].connect(render)

	comp = scene.create(compositeTOP, 'comp')
	comp.nodeX, comp.nodeY = 1000, -300
	comp.inputConnectors[0].connect(feedback)
	comp.inputConnectors[1].connect(render)
	_set(comp, 'operand', 'screen')
	_resolution(comp)

	fade = scene.create(levelTOP, 'fade')
	fade.nodeX, fade.nodeY = 1200, -300
	fade.inputConnectors[0].connect(comp)
	_set(fade, 'inlow', 0.02)
	_expr(fade, 'opacity', '0.7 + 0.15 * {}'.format(audio.format('level')))
	_set(feedback, 'top', fade.name)
	return fade


def _build_tint(scene, trails, audio, clock_value):
	# Mismo shader que la escena vector: lee la densidad en gris y la tiñe
	# con la paleta, fuera del lazo de estelas.
	code = _file_dat(scene, 'tint_code', SHADER_FILE)
	code.nodeX, code.nodeY = 1400, -450

	tint = scene.create(glslTOP, 'tint')
	tint.nodeX, tint.nodeY = 1400, -300
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
	out.nodeX, out.nodeY = 1600, -300
	out.inputConnectors[0].connect(tint)
	out.viewer = True
	return out


def build():
	container = op('/project1') or op('/')
	if container.op(AUDIO_NAME) is None:
		_warn('falta la red de audio; ejecuta primero build_audio.py')
		return
	if getattr(td, 'particlePOP', None) is None:
		_warn('esta version no tiene POPs; hace falta TouchDesigner 2025 o mas nuevo')
		return

	scene = _replace(container, baseCOMP, SCENE_NAME)
	scene.nodeX, scene.nodeY = 0, -1000
	audio_in, clock, wander = _build_clock(scene)
	audio = "op('{}')['{{}}']".format(audio_in.path)
	clock_value = "op('{}')['{{}}']".format(clock.path)
	wander_value = "op('{}')['{{}}']".format(wander.path)
	trail = _build_sim(scene, audio, clock_value, wander_value)
	render = _build_render(scene, trail, audio, wander_value)
	trails = _build_trails(scene, render, audio)
	out = _build_tint(scene, trails, audio, clock_value)

	# Vista de la escena al nivel del proyecto.
	view = _replace(container, selectTOP, VIEW_NAME)
	view.nodeX, view.nodeY = 250, -1000
	_set(view, 'top', '{}/{}'.format(scene.name, out.name))
	view.viewer = True
	_warn('listo: {} y {}'.format(scene.path, view.path))


build()

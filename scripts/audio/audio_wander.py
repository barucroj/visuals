"""Callbacks del Script CHOP de ángulos errantes.

Recibe los canales del análisis de audio y entrega un ángulo en grados por
banda. Cada ángulo da un paseo al azar: su dirección cambia de a poco y sin
saltos, y avanza más rápido cuanto más fuerte suena su banda. En silencio
casi no se mueve. Un golpe puede darle la vuelta a la dirección.
"""

import random

# Nombre del ángulo, banda que lo mueve, grados por segundo en silencio y
# grados por segundo extra con la banda a tope.
WANDERS = (
	('low_angle', 'low', 4.0, 160.0),
	('mid_angle', 'mid', 4.0, 120.0),
	('high_angle', 'high', 4.0, 200.0),
	('level_angle', 'level', 3.0, 90.0),
)

# Qué tanto se tuerce la dirección por segundo y qué tan seguido un golpe
# la invierte.
TURN = 1.8
BEAT_FLIP_CHANCE = 0.35

# Tope del avance por frame, para que una pausa no provoque un salto.
MAX_STEP = 0.1

_state = {
	'last': None,
	'last_beat': 0.0,
	'angles': {},
	'directions': {},
}


def _step(now):
	"""Devuelve los segundos transcurridos desde el frame anterior."""
	last = _state['last']
	_state['last'] = now
	if last is None:
		return 0.0
	return min(max(now - last, 0.0), MAX_STEP)


def _channel(source, name):
	if source is None:
		return 0.0
	chan = source.chan(name)
	return chan.eval() if chan is not None else 0.0


def _direction(name, step, flip):
	direction = _state['directions'].get(name)
	if direction is None:
		direction = random.choice((-1.0, 1.0))
	direction += random.gauss(0.0, TURN) * step ** 0.5
	if flip and random.random() < BEAT_FLIP_CHANCE:
		direction = -direction
	direction = min(max(direction, -1.0), 1.0)
	_state['directions'][name] = direction
	return direction


def onSetupParameters(scriptOp):
	return


def onPulse(par):
	return


def onCook(scriptOp):
	scriptOp.clear()
	scriptOp.numSamples = 1
	scriptOp.rate = scriptOp.time.rate

	source = scriptOp.inputs[0] if scriptOp.inputs else None
	step = _step(absTime.seconds)

	# Un golpe nuevo se nota en el borde de subida de su envolvente.
	beat = _channel(source, 'beat')
	flip = beat > 0.5 and _state['last_beat'] <= 0.5
	_state['last_beat'] = beat

	for name, band, base, boost in WANDERS:
		level = _channel(source, band)
		direction = _direction(name, step, flip)
		angle = _state['angles'].get(name, random.uniform(0.0, 360.0))
		angle = (angle + direction * (base + boost * level) * step) % 360.0
		_state['angles'][name] = angle
		chan = scriptOp.appendChan(name)
		chan[0] = angle
	return

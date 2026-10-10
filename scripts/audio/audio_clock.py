"""Callbacks del Script CHOP de relojes de escena.

Recibe los canales del análisis de audio y entrega relojes en segundos:
seconds avanza a ritmo constante y low_phase y mid_phase avanzan más rápido
cuanto más fuerte suena su banda. Sirven para mover un visual con el audio
sin que salte.
"""

# Nombre del reloj, banda que lo acelera, velocidad en silencio y velocidad
# extra con la banda a tope.
CLOCKS = (
	('seconds', None, 1.0, 0.0),
	('low_phase', 'low', 0.15, 1.6),
	('mid_phase', 'mid', 0.2, 1.0),
)

# Tope del avance por frame, para que una pausa no provoque un salto.
MAX_STEP = 0.1

_state = {
	'last': None,
	'values': {},
}


def _step(now):
	"""Devuelve los segundos transcurridos desde el frame anterior."""
	last = _state['last']
	_state['last'] = now
	if last is None:
		return 0.0
	return min(max(now - last, 0.0), MAX_STEP)


def _advance(name, speed, step):
	value = _state['values'].get(name, 0.0) + speed * step
	_state['values'][name] = value
	return value


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

	for name, band, base, boost in CLOCKS:
		level = 0.0
		if band is not None and source is not None:
			band_chan = source.chan(band)
			if band_chan is not None:
				level = band_chan.eval()
		chan = scriptOp.appendChan(name)
		chan[0] = _advance(name, base + boost * level, step)
	return

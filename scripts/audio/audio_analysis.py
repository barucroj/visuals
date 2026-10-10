"""Callbacks del Script CHOP de análisis de audio.

Recibe audio crudo y entrega un solo sample con los canales low, mid, high
y level, cada uno normalizado al rango 0-1.
"""

import numpy as np

FFT_SIZE = 2048

# Nombre del canal y rango de frecuencias en Hz.
BANDS = (
	('low', 20.0, 250.0),
	('mid', 250.0, 4000.0),
	('high', 4000.0, 16000.0),
)
CHANNELS = tuple(name for name, _, _ in BANDS) + ('level',)

# Suavizado por frame: qué tan rápido sube y qué tan rápido cae el valor.
ATTACK = 0.6
RELEASE = 0.12

# Ganancia automática: cada canal se divide entre su pico reciente.
# PEAK_DECAY controla qué tan rápido se olvida ese pico y NOISE_FLOOR evita
# que el ruido de fondo se amplifique cuando hay silencio.
PEAK_DECAY = 0.999
NOISE_FLOOR = 0.01

_window = np.hanning(FFT_SIZE).astype(np.float32)
_window_gain = _window.sum() / 2.0

_state = {
	'buffer': np.zeros(FFT_SIZE, dtype=np.float32),
	'peaks': {},
	'values': {},
}


def _push(samples):
	"""Agrega las muestras nuevas al final del buffer y descarta las viejas."""
	buffer = _state['buffer']
	count = len(samples)
	if count >= FFT_SIZE:
		buffer[:] = samples[-FFT_SIZE:]
	elif count > 0:
		buffer[:-count] = buffer[count:]
		buffer[-count:] = samples


def _measure(sample_rate):
	"""Devuelve la amplitud cruda de cada banda y el nivel general."""
	buffer = _state['buffer']
	spectrum = np.abs(np.fft.rfft(buffer * _window)) / _window_gain
	freqs = np.fft.rfftfreq(FFT_SIZE, 1.0 / sample_rate)
	raw = {}
	for name, low, high in BANDS:
		band = spectrum[(freqs >= low) & (freqs < high)]
		raw[name] = float(np.sqrt(np.sum(band * band)))
	raw['level'] = float(np.sqrt(np.mean(buffer * buffer)))
	return raw


def _normalize(name, value):
	peak = max(value, _state['peaks'].get(name, 0.0) * PEAK_DECAY, NOISE_FLOOR)
	_state['peaks'][name] = peak
	return value / peak


def _smooth(name, target):
	current = _state['values'].get(name, 0.0)
	rate = ATTACK if target > current else RELEASE
	current += (target - current) * rate
	_state['values'][name] = current
	return current


def onSetupParameters(scriptOp):
	return


def onPulse(par):
	return


def onCook(scriptOp):
	scriptOp.clear()
	scriptOp.numSamples = 1
	scriptOp.rate = scriptOp.time.rate

	raw = dict.fromkeys(CHANNELS, 0.0)
	if scriptOp.inputs and scriptOp.inputs[0].numChans > 0:
		source = scriptOp.inputs[0]
		_push(source.numpyArray().mean(axis=0))
		raw = _measure(source.rate)

	for name in CHANNELS:
		chan = scriptOp.appendChan(name)
		chan[0] = _smooth(name, _normalize(name, raw[name]))
	return

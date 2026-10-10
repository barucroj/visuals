"""Callbacks del Script CHOP de análisis de audio.

Recibe audio crudo y entrega un solo sample con los canales low, mid, high
y level, cada uno normalizado al rango 0-1, más beat y beat_count: beat
salta a 1 en cada golpe de bombo y se apaga, y beat_count cuenta los golpes.
"""

from collections import deque

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

# Detección de beat: hay golpe cuando la energía del bombo sube de un frame
# al siguiente bastante más que en los frames recientes.
KICK_RANGE = (40.0, 150.0)

# El bombo se mide contra su pico reciente, pero nunca contra menos que esta
# proporción del nivel general: así el ruido sin graves no cuenta como golpe.
KICK_MIN_SHARE = 1.0

# Frames recientes contra los que se compara la subida.
BEAT_HISTORY = 45

# Cuántas desviaciones sobre el promedio debe superar la subida, y la subida
# mínima aceptada. Bajar estos valores detecta más golpes.
BEAT_SENSITIVITY = 2.0
BEAT_MIN_RISE = 0.15

# Segundos mínimos entre dos golpes y caída por frame del canal beat.
BEAT_MIN_INTERVAL = 0.25
BEAT_DECAY = 0.85

_window = np.hanning(FFT_SIZE).astype(np.float32)
_window_gain = _window.sum() / 2.0

_state = {
	'buffer': np.zeros(FFT_SIZE, dtype=np.float32),
	'peaks': {},
	'values': {},
	'kick': 0.0,
	'rises': deque(maxlen=BEAT_HISTORY),
	'since_beat': BEAT_MIN_INTERVAL,
	'beat': 0.0,
	'beat_count': 0,
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
	kick = spectrum[(freqs >= KICK_RANGE[0]) & (freqs < KICK_RANGE[1])]
	raw['kick'] = float(np.sqrt(np.sum(kick * kick)))
	return raw


def _detect_beat(kick, level, elapsed):
	"""Actualiza beat y beat_count con la energía del bombo de este frame."""
	peak = max(kick, _state['peaks'].get('kick', 0.0) * PEAK_DECAY, KICK_MIN_SHARE * level, NOISE_FLOOR)
	_state['peaks']['kick'] = peak
	kick /= peak
	rise = max(kick - _state['kick'], 0.0)
	_state['kick'] = kick

	rises = _state['rises']
	threshold = BEAT_MIN_RISE
	if rises:
		threshold = max(threshold, np.mean(rises) + BEAT_SENSITIVITY * np.std(rises))
	rises.append(rise)

	_state['since_beat'] += elapsed
	_state['beat'] *= BEAT_DECAY
	if rise > threshold and _state['since_beat'] >= BEAT_MIN_INTERVAL:
		_state['since_beat'] = 0.0
		_state['beat'] = 1.0
		_state['beat_count'] += 1


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

	raw = dict.fromkeys(CHANNELS + ('kick',), 0.0)
	elapsed = 0.0
	if scriptOp.inputs and scriptOp.inputs[0].numChans > 0:
		source = scriptOp.inputs[0]
		samples = source.numpyArray().mean(axis=0)
		_push(samples)
		raw = _measure(source.rate)
		elapsed = len(samples) / source.rate
	_detect_beat(raw['kick'], raw['level'], elapsed)

	for name in CHANNELS:
		chan = scriptOp.appendChan(name)
		chan[0] = _smooth(name, _normalize(name, raw[name]))
	scriptOp.appendChan('beat')[0] = _state['beat']
	scriptOp.appendChan('beat_count')[0] = _state['beat_count']
	return

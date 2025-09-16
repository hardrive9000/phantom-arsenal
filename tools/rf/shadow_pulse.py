#!/usr/bin/env python3
"""
SHADOW PULSE v1.0 - Advanced RF Signal Replay Tool
Infiltrates electromagnetic spectrum, extracts pulse patterns,
and executes precision RF replay operations.

Usage: python3 shadow_pulse.py <cu8_file> [options]
"""

import numpy as np
import RPi.GPIO as GPIO
import time
import argparse
import sys
from datetime import datetime

class CU8ReplayDevice:
    def __init__(self, gpio_pin=18, sample_rate=250000):
        """
        Inicializa el dispositivo de replay

        Args:
            gpio_pin (int): Pin GPIO del transmisor
            sample_rate (int): Frecuencia de muestreo del archivo cu8
        """
        self.gpio_pin = gpio_pin
        self.sample_rate = sample_rate
        self.time_per_sample = 1.0 / sample_rate
        self.pulse_data = []
        self.gap_data = []
        self.setup_gpio()

        print(f"GPIO {gpio_pin} configurado para transmision")
        print(f"Resolucion temporal: {self.time_per_sample * 1e6:.1f}μs por muestra")

    def setup_gpio(self):
        """Configura el GPIO para transmision"""
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.gpio_pin, GPIO.OUT)
        GPIO.output(self.gpio_pin, GPIO.LOW)

    def load_and_analyze_cu8(self, filename, threshold_factor=3.0, min_pulse_samples=10):
        """
        Carga archivo cu8, analiza y extrae pulsos en una sola operacion

        Args:
            filename (str): Archivo cu8 a procesar
            threshold_factor (float): Factor para threshold automatico
            min_pulse_samples (int): Minimo de muestras para pulso valido

        Returns:
            bool: True si se extrajo la senial correctamente
        """
        print(f"Cargando {filename}...")

        try:
            # Cargar archivo cu8
            with open(filename, 'rb') as f:
                raw_data = f.read()

            file_size_mb = len(raw_data) / (1024 * 1024)
            duration_sec = (len(raw_data) // 2) * self.time_per_sample

            print(f"Archivo: {file_size_mb:.1f}MB, Duracion: {duration_sec:.2f}s")

            # Procesar datos IQ
            amplitude = self._process_iq_data(raw_data)
            if amplitude is None:
                return False

            # Detectar pulsos
            success = self._detect_pulses(amplitude, threshold_factor, min_pulse_samples)

            if success and self.pulse_data:
                self._analyze_signal_structure()
                return True
            else:
                print("No se detectaron pulsos validos")
                return False

        except FileNotFoundError:
            print(f"Error: No se encontro el archivo {filename}")
            return False
        except Exception as e:
            print(f"Error procesando archivo: {e}")
            return False

    def _process_iq_data(self, raw_data):
        """Procesa datos IQ raw y calcula amplitud"""
        try:
            # Convertir a muestras IQ
            iq_data = np.frombuffer(raw_data, dtype=np.uint8).astype(np.float32)
            iq_data = iq_data - 127.5  # Centrar en 0

            # Separar I y Q
            i_samples = iq_data[0::2]
            q_samples = iq_data[1::2]

            # Calcular amplitud
            amplitude = np.sqrt(i_samples**2 + q_samples**2)

            print(f"Muestras: {len(amplitude):,}, Rango amplitud: {np.min(amplitude):.1f} - {np.max(amplitude):.1f}")

            return amplitude

        except Exception as e:
            print(f"Error procesando datos IQ: {e}")
            return None

    def _detect_pulses(self, amplitude, threshold_factor, min_pulse_samples):
        """Detecta pulsos y gaps en la senial"""
        # Calcular threshold automatico
        noise_floor = np.percentile(amplitude, 10)  # 10% mas bajo como ruido
        signal_peak = np.percentile(amplitude, 95)   # 95% como pico
        threshold = noise_floor + (signal_peak - noise_floor) / threshold_factor

        print(f"Ruido: {noise_floor:.1f}, Pico: {signal_peak:.1f}, Threshold: {threshold:.1f}")

        # Detectar senial alta/baja
        signal_high = amplitude > threshold

        # Encontrar transiciones
        transitions = np.diff(signal_high.astype(int))
        rising_edges = np.where(transitions == 1)[0] + 1
        falling_edges = np.where(transitions == -1)[0] + 1

        # Sincronizar flancos
        if len(falling_edges) > 0 and len(rising_edges) > 0:
            if falling_edges[0] < rising_edges[0]:
                falling_edges = falling_edges[1:]

        min_edges = min(len(rising_edges), len(falling_edges))
        rising_edges = rising_edges[:min_edges]
        falling_edges = falling_edges[:min_edges]

        if min_edges == 0:
            print("No se detectaron transiciones validas")
            return False

        print(f"Transiciones: {min_edges} pulsos detectados")

        # Extraer duraciones
        pulses = []
        gaps = []

        for i in range(len(rising_edges)):
            # Duracion del pulso
            pulse_samples = falling_edges[i] - rising_edges[i]
            if pulse_samples >= min_pulse_samples:
                pulse_duration_us = int(pulse_samples * self.time_per_sample * 1e6)
                pulses.append(pulse_duration_us)

                # Duracion del gap
                if i < len(rising_edges) - 1:
                    gap_samples = rising_edges[i + 1] - falling_edges[i]
                    gap_duration_us = int(gap_samples * self.time_per_sample * 1e6)
                    gaps.append(gap_duration_us)

        self.pulse_data = pulses
        self.gap_data = gaps

        print(f"Extraidos: {len(pulses)} pulsos, {len(gaps)} gaps")

        if pulses:
            print(f"Rango pulsos: {min(pulses)} - {max(pulses)}μs")
            if gaps:
                print(f"Rango gaps: {min(gaps)} - {max(gaps)}μs")
            return True

        return False

    def _analyze_signal_structure(self):
        """Analiza estructura de la senial detectada"""
        if not self.pulse_data:
            return

        print(f"\n=== ANALISIS ===")

        # Agrupar pulsos similares
        pulse_groups = self._group_durations(self.pulse_data)
        print(f"Tipos de PULSOS ({len(pulse_groups)}):")
        for i, (duration, count) in enumerate(pulse_groups.items()):
            print(f"   [{i}] {duration:,}μs (x{count})")

        # Agrupar gaps si existen
        if self.gap_data:
            gap_groups = self._group_durations(self.gap_data)
            print(f"Tipos de GAPS ({len(gap_groups)}):")
            for i, (duration, count) in enumerate(gap_groups.items()):
                print(f"   [{i}] {duration:,}μs (x{count})")

            # Detectar separadores de mensaje
            gap_list = list(gap_groups.keys())
            if len(gap_list) >= 2:
                longest_gap = max(gap_list)
                regular_gaps = [g for g in gap_list if g < longest_gap / 2]

                if regular_gaps and longest_gap > max(regular_gaps) * 2:
                    separators = gap_groups[longest_gap]
                    messages = separators + 1
                    bits_per_msg = len(self.pulse_data) // messages

                    print(f"Estructura detectada:")
                    print(f"   Mensajes: {messages}")
                    print(f"   Separadores: {separators} de {longest_gap:,}μs")
                    print(f"   Bits por mensaje: ~{bits_per_msg}")

    def _group_durations(self, durations, tolerance=0.15):
        """Agrupa duraciones similares"""
        if not durations:
            return {}

        groups = {}
        remaining = list(durations)

        while remaining:
            reference = remaining.pop(0)
            group = [reference]

            # Buscar duraciones similares
            to_remove = []
            for duration in remaining:
                if abs(duration - reference) <= max(reference * tolerance, 20):  # 20μs minimo
                    group.append(duration)
                    to_remove.append(duration)

            # Remover agrupadas
            for duration in to_remove:
                remaining.remove(duration)

            # Promedio del grupo
            avg_duration = int(sum(group) / len(group))
            groups[avg_duration] = len(group)

        return dict(sorted(groups.items()))

    def replay_signal(self, repetitions=1, delay_between_reps=0.1):
        """
        Reproduce la senial extraida en el GPIO

        Args:
            repetitions (int): Numero de veces a repetir toda la secuencia
            delay_between_reps (float): Pausa entre repeticiones completas (segundos)
        """
        if not self.pulse_data:
            print("No hay datos de pulsos para reproducir")
            return False

        total_duration = sum(self.pulse_data) + sum(self.gap_data)

        print(f"\n=== REPRODUCIENDO ===")
        print(f"Pulsos: {len(self.pulse_data)}, Gaps: {len(self.gap_data)}")
        print(f"Duracion por repeticion: {total_duration/1000:.1f}ms")
        print(f"Repeticiones: {repetitions}")
        print(f"Inicio: {datetime.now().strftime('%H:%M:%S')}")

        try:
            for rep in range(repetitions):
                print(f"Repeticion {rep + 1}/{repetitions}...", end=" ", flush=True)

                start_time = time.time()

                # Transmitir secuencia
                for i in range(len(self.pulse_data)):
                    # Pulso HIGH
                    GPIO.output(self.gpio_pin, GPIO.HIGH)
                    time.sleep(self.pulse_data[i] / 1_000_000)

                    # Gap LOW (si existe)
                    if i < len(self.gap_data):
                        GPIO.output(self.gpio_pin, GPIO.LOW)
                        time.sleep(self.gap_data[i] / 1_000_000)

                # Asegurar LOW final
                GPIO.output(self.gpio_pin, GPIO.LOW)

                elapsed = time.time() - start_time
                print(f"{elapsed*1000:.1f}ms")

                # Pausa entre repeticiones
                if rep < repetitions - 1:
                    time.sleep(delay_between_reps)

            print(f"Transmision completada: {datetime.now().strftime('%H:%M:%S')}")
            return True

        except KeyboardInterrupt:
            print(f"\nTransmision interrumpida por usuario")
            return False
        except Exception as e:
            print(f"\nError durante transmision: {e}")
            return False
        finally:
            GPIO.output(self.gpio_pin, GPIO.LOW)

    def cleanup(self):
        """Limpia recursos GPIO"""
        GPIO.cleanup()
        print(f"GPIO limpiado")

def main():
    parser = argparse.ArgumentParser(
        description='Replay RF 433MHz desde archivo cu8',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python3 cu8_replay.py signal.cu8                    # Replay basico
  python3 cu8_replay.py signal.cu8 -p 22 -r 5        # Pin 22, 5 repeticiones
  python3 cu8_replay.py signal.cu8 -t 2.5 -s 1000000 # Threshold 2.5, 1MHz
  python3 cu8_replay.py signal.cu8 --analyze-only     # Solo analisis, no transmitir
        """
    )

    parser.add_argument('cu8_file', help='Archivo cu8 a procesar')
    parser.add_argument('-p', '--pin', type=int, default=18,
                       help='Pin GPIO del transmisor (default: 18)')
    parser.add_argument('-r', '--repetitions', type=int, default=1,
                       help='Numero de repeticiones (default: 1)')
    parser.add_argument('-s', '--sample-rate', type=int, default=250000,
                       help='Frecuencia de muestreo Hz (default: 250000)')
    parser.add_argument('-t', '--threshold', type=float, default=3.0,
                       help='Factor de threshold (default: 3.0)')
    parser.add_argument('-d', '--delay', type=float, default=0.1,
                       help='Pausa entre repeticiones seg (default: 0.1)')
    parser.add_argument('--min-pulse', type=int, default=10,
                       help='Minimo muestras por pulso (default: 10)')
    parser.add_argument('--analyze-only', action='store_true',
                       help='Solo analizar, no transmitir')

    args = parser.parse_args()

    print(f"=== CU8 REPLAY TOOL ===")
    print(f"Archivo: {args.cu8_file}")
    print(f"GPIO: {args.pin}")
    print(f"Sample rate: {args.sample_rate:,} Hz")

    # Crear dispositivo
    replay_device = CU8ReplayDevice(args.pin, args.sample_rate)

    try:
        # Cargar y analizar
        if not replay_device.load_and_analyze_cu8(
            args.cu8_file,
            args.threshold,
            args.min_pulse
        ):
            print("Fallo en analisis del archivo")
            return 1

        # Transmitir si no es solo analisis
        if not args.analyze_only:
            if replay_device.replay_signal(args.repetitions, args.delay):
                print("Replay completado exitosamente")
            else:
                print("Error durante el replay")
                return 1
        else:
            print("Analisis completado (modo solo-analisis)")

    except KeyboardInterrupt:
        print(f"\nPrograma interrumpido por usuario")
    except Exception as e:
        print(f"Error inesperado: {e}")
        return 1
    finally:
        replay_device.cleanup()

    return 0

if __name__ == "__main__":
    sys.exit(main())

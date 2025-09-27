#!/usr/bin/env python3
import serial
import time
import signal
import sys
import os

class GPSCommander:
    def __init__(self, port='/dev/ttyS0', baud=9600):
        self.port = port
        self.baud = baud
        self.ser = None
        self.connect()

    def connect(self):
        """Conectar con reintentos y limpieza"""
        if self.ser and self.ser.is_open:
            try:
                self.ser.close()
            except:
                pass
            time.sleep(1)

        max_retries = 3
        for attempt in range(max_retries):
            try:
                print(f"Intentando conectar ({attempt + 1}/{max_retries})...")

                # Configurar puerto antes de abrir
                os.system(f'stty -F {self.port} {self.baud} raw -echo')
                time.sleep(0.5)

                self.ser = serial.Serial(
                    port=self.port,
                    baudrate=self.baud,
                    timeout=0.1,
                    write_timeout=0.1,
                    exclusive=True  # Evita que otros procesos usen el puerto
                )

                # Limpiar buffers
                self.ser.reset_input_buffer()
                self.ser.reset_output_buffer()
                time.sleep(0.5)

                print(f"✓ Conectado a {self.port} a {self.baud} bps")
                return True

            except Exception as e:
                print(f"✗ Error en intento {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)
                else:
                    print("No se pudo conectar al GPS")
                    return False

    def reconnect(self):
        """Reconectar cuando hay problemas"""
        print("Reconectando...")
        return self.connect()

    def send_command(self, command):
        if not self.ser or not self.ser.is_open:
            if not self.reconnect():
                return None

        try:
            # Limpiar buffers antes de enviar
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
            time.sleep(0.1)

            # Preparar comando
            if not command.startswith('$'):
                command = f'${command}'

            # Enviar comando
            self.ser.write(f'{command}\r\n'.encode())
            self.ser.flush()  # Asegurar que se envia
            print(f">> {command}")

            # Esperar respuesta
            start_time = time.time()
            responses = []

            while time.time() - start_time < 3:
                try:
                    if self.ser.in_waiting > 0:
                        line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                        if line:
                            responses.append(line)
                            if 'PMTK' in line or 'ACK' in line:
                                print(f"<< {line}")
                                return line
                    time.sleep(0.01)
                except Exception as e:
                    print(f"Error leyendo: {e}")
                    break

            if responses:
                print(f"<< Otras respuestas: {len(responses)} lineas")
                for resp in responses[-3:]:  # Mostrar las ultimas 3
                    if resp.strip():
                        print(f"   {resp}")
            else:
                print("<< Sin respuesta")

            return None

        except Exception as e:
            print(f"✗ Error enviando comando: {e}")
            # Intentar reconectar
            self.reconnect()
            return None

    def monitor(self, duration=5):
        if not self.ser or not self.ser.is_open:
            if not self.reconnect():
                return

        print(f"Monitoreando por {duration} segundos... (Ctrl+C para parar)")
        try:
            start_time = time.time()
            while time.time() - start_time < duration:
                if self.ser.in_waiting > 0:
                    line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                    if line:
                        print(line)
                time.sleep(0.01)
        except KeyboardInterrupt:
            print("\nMonitoreo detenido")
        except Exception as e:
            print(f"Error monitoreando: {e}")

    def close(self):
        if self.ser and self.ser.is_open:
            try:
                self.ser.close()
                print("✓ Conexion cerrada")
            except:
                pass

# Script principal con manejo de seniales
gps = None

def signal_handler(sig, frame):
    print('\n\nCerrando aplicacion...')
    if gps:
        gps.close()
    sys.exit(0)

def reset_port():
    """Funcion para resetear el puerto manualmente"""
    print("Reseteando puerto serie...")
    os.system('sudo pkill -f serial 2>/dev/null')
    os.system('stty -F /dev/serial0 sane')
    os.system('stty -F /dev/serial0 9600')
    time.sleep(1)
    print("Puerto reseteado")

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)

    print("=== GPS MT3339 Commander v2 ===")
    print("Comandos:")
    print("  PMTK605*31    - Ver firmware")
    print("  PMTK414*33    - Ver config NMEA")
    print("  PMTK101*32    - Hot restart")
    print("  monitor       - Ver datos NMEA")
    print("  reconnect     - Reconectar")
    print("  reset         - Resetear puerto")
    print("  quit          - Salir")
    print("===============================\n")

    gps = GPSCommander()

    try:
        while True:
            cmd = input("GPS> ").strip()

            if cmd.lower() in ['quit', 'exit']:
                break
            elif cmd.lower() == 'monitor':
                gps.monitor(10)
            elif cmd.lower() == 'reconnect':
                gps.reconnect()
            elif cmd.lower() == 'reset':
                gps.close()
                reset_port()
                gps = GPSCommander()
            elif cmd:
                gps.send_command(cmd)

    except KeyboardInterrupt:
        print("\nInterrumpido por usuario")
    finally:
        if gps:
            gps.close()

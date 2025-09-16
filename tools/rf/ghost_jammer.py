#!/usr/bin/env python3
"""
GHOST JAMMER v1.0 - Phantom signal generator (15KHz electromagnetic pulse emission)
Deploys synthetic square waves through GPIO neural interface
WARNING: For authorized personnel only. Monitor spectral output via oscilloscope.

Target: Raspberry Pi Zero 2W | Neural Node: GPIO 18 | Frequency: 15.000 kHz
"""

import RPi.GPIO as GPIO
import time
import signal
import sys

# Configuracion
GPIO_PIN = 18  # Pin GPIO donde conectas el osciloscopio
FREQUENCY = 15000  # 15KHz
DUTY_CYCLE = 50  # 50% duty cycle para onda cuadrada perfecta
gpio_initialized = False  # Flag para controlar si GPIO fue inicializado

def cleanup_gpio():
    """Limpia GPIO solo si fue inicializado"""
    global gpio_initialized
    if gpio_initialized:
        GPIO.cleanup()
        gpio_initialized = False

def signal_handler(sig, frame):
    """Maneja la interrupcion del programa (Ctrl+C)"""
    print("\nDeteniendo generacion de onda cuadrada...")
    cleanup_gpio()
    sys.exit(0)

def setup_gpio():
    """Configura el pin GPIO"""
    global gpio_initialized
    GPIO.setmode(GPIO.BCM)  # Usar numeracion BCM
    GPIO.setup(GPIO_PIN, GPIO.OUT)
    gpio_initialized = True
    print(f"GPIO {GPIO_PIN} configurado como salida")

def generate_square_wave_pwm():
    """
    Genera onda cuadrada usando PWM de RPi.GPIO
    Metodo mas preciso para frecuencias altas
    """
    print(f"Iniciando generacion de onda cuadrada de {FREQUENCY}Hz en GPIO {GPIO_PIN}")
    print("Presiona Ctrl+C para detener")
    
    # Crear objeto PWM
    pwm = GPIO.PWM(GPIO_PIN, FREQUENCY)
    
    try:
        # Iniciar PWM con duty cycle del 50%
        pwm.start(DUTY_CYCLE)
        
        # Mantener la senial funcionando
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        pass
    finally:
        pwm.stop()

def generate_square_wave_manual():
    """
    Genera onda cuadrada manualmente (metodo alternativo)
    Menos preciso para frecuencias altas, pero util para entender el concepto
    """
    # Calcular periodo y tiempos
    period = 1.0 / FREQUENCY  # Periodo en segundos
    half_period = period / 2  # Tiempo en HIGH y LOW
    
    print(f"Metodo manual - Periodo: {period*1000:.3f}ms, Medio periodo: {half_period*1000000:.1f}μs")
    print("ADVERTENCIA: Este metodo puede no ser preciso para 15KHz")
    
    try:
        while True:
            GPIO.output(GPIO_PIN, GPIO.HIGH)
            time.sleep(half_period)
            GPIO.output(GPIO_PIN, GPIO.LOW)
            time.sleep(half_period)
    except KeyboardInterrupt:
        pass

def main():
    """Funcion principal"""
    print("=== Generador de Onda Cuadrada 15KHz ===")
    print(f"Pin GPIO: {GPIO_PIN}")
    print(f"Frecuencia: {FREQUENCY} Hz")
    print(f"Duty Cycle: {DUTY_CYCLE}%")
    print()
    
    # Configurar manejo de seniales
    signal.signal(signal.SIGINT, signal_handler)
    
    # Configurar GPIO
    setup_gpio()
    
    # Elegir metodo de generacion
    print("Metodos disponibles:")
    print("1. PWM (Recomendado para 15KHz)")
    print("2. Manual (Solo para demostracion)")
    
    try:
        choice = input("\nSelecciona metodo (1 o 2): ").strip()
        
        if choice == "1":
            generate_square_wave_pwm()
        elif choice == "2":
            generate_square_wave_manual()
        else:
            print("Opcion invalida, usando PWM por defecto")
            generate_square_wave_pwm()
            
    except KeyboardInterrupt:
        pass
    finally:
        cleanup_gpio()
        print("\nGPIO limpiado. Programa terminado.")

if __name__ == "__main__":
    main()

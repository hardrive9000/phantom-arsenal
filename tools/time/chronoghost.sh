#!/bin/bash

# Script para sincronizar fecha y hora usando GPS para Kismet Wardriving
# Puerto: /dev/rfcomm0 a 4800 baudios
# Uso: ./chronoghost.sh [interfaz_wifi]

# Configuracion
# GPS_PORT="/dev/rfcomm0"
GPS_PORT="/dev/ttyS0"
# BAUD_RATE="4800"
BAUD_RATE="9600"
TIMEOUT=30
WIFI_INTERFACE="${1:-wlan1}"  # Usar parametro o wlan1 por defecto

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Funcion para parsear sentencia GPRMC del GPS
parse_gprmc() {
    local gprmc_line="$1"

    # Verificar si es una sentencia GPRMC valida
    if [[ ! "$gprmc_line" =~ ^\$GPRMC ]]; then
        return 1
    fi

    # Dividir la sentencia por comas
    IFS=',' read -ra fields <<< "$gprmc_line"

    # Verificar que tenemos suficientes campos y que el status es valido (A = Active)
    if [ ${#fields[@]} -lt 10 ] || [ "${fields[2]}" != "A" ]; then
        return 1
    fi

    local time_utc="${fields[1]}"    # HHMMSS.sss
    local date_utc="${fields[9]}"    # DDMMYY

    # Verificar que tenemos datos validos
    if [ -z "$time_utc" ] || [ -z "$date_utc" ] || [ ${#time_utc} -lt 6 ] || [ ${#date_utc} -lt 6 ]; then
        return 1
    fi

    # Extraer componentes de tiempo
    local hours="${time_utc:0:2}"
    local minutes="${time_utc:2:2}"
    local seconds="${time_utc:4:2}"

    # Extraer componentes de fecha
    local day="${date_utc:0:2}"
    local month="${date_utc:2:2}"
    local year="20${date_utc:4:2}"  # Asumiendo siglo XXI

    # Verificar rangos validos
    if [ "$hours" -gt 23 ] || [ "$minutes" -gt 59 ] || [ "$seconds" -gt 59 ] ||
       [ "$day" -lt 1 ] || [ "$day" -gt 31 ] || [ "$month" -lt 1 ] || [ "$month" -gt 12 ]; then
        return 1
    fi

    # Formato para el comando date: MMDDhhmmYYYY.ss
    GPS_DATETIME="${month}${day}${hours}${minutes}${year}.${seconds}"
    GPS_READABLE="${year}-${month}-${day} ${hours}:${minutes}:${seconds} UTC"

    return 0
}

# Funcion principal para obtener y establecer la hora GPS
sync_time_with_gps() {
    local start_time=$(date +%s)

    echo -e "${YELLOW}Iniciando sincronizacion con GPS...${NC}"
    echo "Leyendo datos GPS (timeout: ${TIMEOUT}s)..."

    while IFS= read -r -t "$TIMEOUT" line; do
        # Verificar timeout
        local current_time=$(date +%s)
        if [ $((current_time - start_time)) -gt "$TIMEOUT" ]; then
            echo -e "${RED}Timeout: No se recibieron datos GPS validos en $TIMEOUT segundos${NC}"
            return 1
        fi

        # Procesar solo sentencias GPRMC
        if [[ "$line" =~ ^\$GPRMC ]]; then
            if parse_gprmc "$line"; then
                echo -e "${GREEN}Datos GPS validos obtenidos: $GPS_READABLE${NC}"

                # Mostrar hora actual antes del cambio
                echo "Hora UTC actual: $(date -u)"
                echo "Hora local actual (Argentina): $(date)"

                # Establecer la nueva hora en UTC (sistema ya tiene timezone -3 configurada)
                if date -u "$GPS_DATETIME" >/dev/null 2>&1; then
                    echo -e "${GREEN}Hora UTC sincronizada exitosamente${NC}"
                    echo "Hora UTC establecida: $(date -u)"
                    echo "Hora local (Argentina UTC-3): $(date)"

                    # Ejecutar airmon-ng despues de sincronizacion exitosa
                    echo -e "${YELLOW}Iniciando modo monitor en $WIFI_INTERFACE...${NC}"
                    if command -v airmon-ng >/dev/null 2>&1; then
                        airmon-ng start "$WIFI_INTERFACE"
                        if [ $? -eq 0 ]; then
                            echo -e "${GREEN}Modo monitor activado en $WIFI_INTERFACE${NC}"
                            echo -e "${GREEN}kismet --no-ncurses --override wardrive${NC}"
                        else
                            echo -e "${YELLOW}Advertencia: Error al activar modo monitor${NC}"
                        fi
                    else
                        echo -e "${YELLOW}Advertencia: airmon-ng no encontrado${NC}"
                    fi

                    return 0
                else
                    echo -e "${RED}Error al establecer la fecha/hora del sistema${NC}"
                    return 1
                fi
            fi
        fi
    done < "$GPS_PORT"

    echo -e "${RED}No se pudieron obtener datos GPS validos${NC}"
    return 1
}

# Verificar permisos de root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Este script requiere permisos de administrador${NC}"
    echo "Ejecuta con: sudo $0"
    exit 1
fi

# Mostrar ayuda si se solicita
if [[ "$1" == "-h" || "$1" == "--help" ]]; then
    echo "Uso: $0 [interfaz_wifi]"
    echo "Ejemplo: $0 wlan0"
    echo "Por defecto usa wlan1 si no se especifica interfaz"
    exit 0
fi

# Bind RFCOMM
rfcomm bind hci0 E0:DC:FF:16:6C:08 4

# Verificar si el puerto existe
if [ ! -e "$GPS_PORT" ]; then
    echo -e "${RED}Error: Puerto GPS $GPS_PORT no encontrado${NC}"
    echo "El script se abortara."
    exit 1
fi

echo -e "${GREEN}Puerto $GPS_PORT encontrado${NC}"

# Verificar si la interfaz WiFi existe
if [ ! -d "/sys/class/net/$WIFI_INTERFACE" ]; then
    echo -e "${RED}Error: Interfaz WiFi '$WIFI_INTERFACE' no encontrada${NC}"
    echo "Interfaces disponibles:"
    ls /sys/class/net/ | grep -E '^wl|^eth' | sed 's/^/  /'
    exit 1
fi

echo -e "${GREEN}Interfaz WiFi '$WIFI_INTERFACE' encontrada${NC}"

# Configurar el puerto serie
if command -v stty >/dev/null 2>&1; then
    stty -F "$GPS_PORT" "$BAUD_RATE" cs8 -cstopb -parenb raw
    echo "Puerto serie configurado a $BAUD_RATE baudios"
fi

# Ejecutar sincronizacion
echo "=== Sincronizacion de hora GPS ==="
echo "Puerto: $GPS_PORT"
echo "Baudios: $BAUD_RATE"
echo "Timeout: ${TIMEOUT}s"
echo "Interfaz WiFi: $WIFI_INTERFACE"
echo "================================"

if sync_time_with_gps; then
    echo -e "${GREEN}Sincronizacion completada exitosamente${NC}"
    exit 0
else
    echo -e "${RED}Error en la sincronizacion${NC}"
    exit 1
fi

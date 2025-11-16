#!/bin/bash

# ==========================================
#   SPECTRE ACCESS v1.0 - WiFi QR Gateway
#   Quantum encryption key visualization
# ==========================================
# Generates quantum-encoded access portals (QR codes) for wireless networks
# Supports WPA/WEP/Open authentication protocols
# Features:
# - Special character sanitization for secure encoding
# - Hidden SSID support
# - UTF8 terminal visualization
# - PNG export capability
# - Timestamp-based file naming
# ==========================================

escape_special_chars() {
    local input="$1"
    # Escapar los caracteres especiales: \ ; , : "
    # El orden es importante: primero \ para no escapar los escapes que agreguemos
    input="${input//\\/\\\\}"  # Escapar backslash
    input="${input//;/\\;}"    # Escapar punto y coma
    input="${input//,/\\,}"    # Escapar coma
    input="${input//:/\\:}"    # Escapar dos puntos
    input="${input//\"/\\\"}"  # Escapar comillas dobles
    echo "$input"
}

echo "=== Generador de QR para WiFi ==="
read -p "SSID: " ssid
read -sp "Password: " password
echo
read -p "Tipo de seguridad [WPA/WEP/nopass] (default: WPA): " security
security=${security:-WPA}
read -p "¿Red oculta? (s/n, default: n): " hidden

# Sanear los inputs
ssid_escaped=$(escape_special_chars "$ssid")
password_escaped=$(escape_special_chars "$password")

# Determinar si la red esta oculta
if [ "$hidden" = "s" ] || [ "$hidden" = "S" ]; then
    hidden_flag="true"
else
    hidden_flag="false"
fi

# Construir el string del QR
if [ "$security" = "nopass" ]; then
    qr_string="WIFI:T:nopass;S:${ssid_escaped};;"
else
    qr_string="WIFI:T:${security};S:${ssid_escaped};P:${password_escaped};H:${hidden_flag};;"
fi

echo -e "\n=== Escanea este codigo QR con tu smartphone ==="
echo "Red: $ssid"
echo "Seguridad: $security"
echo

# Generar el QR
qrencode -t UTF8 -s 6 "$qr_string"

# Opcion para guardar como imagen
echo
read -p "¿Guardar tambien como imagen PNG? (s/n): " save_image
if [ "$save_image" = "s" ] || [ "$save_image" = "S" ]; then
    filename="wifi_${ssid// /_}_$(date +%Y%m%d_%H%M%S).png"
    qrencode -o "$filename" "$qr_string"
    echo "Guardado como: $filename"
fi

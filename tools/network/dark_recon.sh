#!/bin/bash
# ==========================================
#   DARK RECON v1.0 - Advanced Network Intelligence
#   Deep reconnaissance with SMB infiltration
# ==========================================
# Advanced network mapping and SMB resource enumeration
# Features:
# - Secure WiFi connection (credentials in temp file chmod 600)
# - Interactive SMB shell with anonymous/authenticated access
# - Process and IP cleanup on exit
# - Dependency verification
# - Share enumeration and browsing capabilities
# ==========================================

RED="\e[31m"; GREEN="\e[32m"; YELLOW="\e[33m"; BLUE="\e[34m"; NC="\e[0m"

check_dep() { command -v "$1" >/dev/null 2>&1 || { echo -e "${RED}Not installed:${NC} $1"; exit 1; }; }

restore_addrs() {
    ip addr flush dev "$IFACE" 2>/dev/null || true
    if [ "$had_ip" = "1" ]; then
        for cidr in "${ORIG_IPV4[@]}"; do
            ip addr add "$cidr" dev "$IFACE" 2>/dev/null || true
        done
    fi
}

# Function to list devices
list_devices() {
    echo -e "${BLUE}=== Devices on network ===${NC}"
    nmap -sn -e "$IFACE" "$NETWORK" 2>/dev/null | awk '
        /Nmap scan report/ {ip=$NF}
        /MAC Address:/ {print ip " - " $0}
    '
    echo ""
}

# Function to execute SMB shell
execute_smb_shell() {
    local target_ip="$1"

    echo -e "\n${GREEN}Connecting to $target_ip...${NC}"
    echo -e "${YELLOW}Useful commands in smbclient:${NC}"
    echo "  ls                 - List files"
    echo "  cd <directory>     - Change directory"
    echo "  get <file>         - Download file"
    echo "  put <file>         - Upload file"
    echo "  help               - Show help"
    echo "  exit               - Exit SMB shell"
    echo ""

    while true; do
        echo -e "${BLUE}Connection options for $target_ip:${NC}"
        echo "1) Anonymous connection"
        echo "2) Connection with credentials"
        echo "3) List shared resources"
        echo "4) Return to host selection"
        echo -n "Select an option: "
        read -r conn_option

        case "$conn_option" in
            1)
                echo -n "Enter share name: "
                read -r share_name
                if [ -n "$share_name" ]; then
                    echo -e "${GREEN}Starting anonymous connection to //$target_ip/$share_name${NC}"
                    (
                        trap 'echo -e "\n${YELLOW}Closing SMB connection...${NC}"' EXIT
                        smbclient -N "//$target_ip/$share_name"
                    )
                    echo -e "${GREEN}SMB session finished, returning to menu...${NC}"
                else
                    echo -e "${RED}Empty share name, canceling...${NC}"
                fi
                ;;
            2)
                echo -n "Enter share name: "
                read -r share_name

                if [ -n "$share_name" ]; then
                    echo -n "Username: "
                    read -r smb_user
                    echo -n "Domain (optional): "
                    read -r smb_domain

                    if [ -n "$smb_domain" ]; then
                        smb_user="$smb_domain\\$smb_user"
                    fi

                    echo -e "${GREEN}Starting connection with credentials to //$target_ip/$share_name${NC}"
                    (
                        trap 'echo -e "\n${YELLOW}Closing SMB connection...${NC}"' EXIT
                        smbclient "//$target_ip/$share_name" -U "$smb_user"
                    )
                    echo -e "${GREEN}SMB session finished, returning to menu...${NC}"
                else
                    echo -e "${RED}Empty share name, canceling...${NC}"
                fi
                ;;
            3)
                echo -e "${GREEN}Listing shared resources on $target_ip:${NC}"
                smbclient -L "//$target_ip" -N 2>/dev/null || echo " Could not access"
                echo ""
                ;;
            4)
                break
                ;;
            *)
                echo -e "${RED}Invalid option${NC}"
                ;;
        esac

        read -p "Press Enter to continue..." -r
    done
}

# Function to handle interactive SMB shell
interactive_smb_shell() {
    local hosts=("$@")
    local selected_host=""

    while true; do
        echo -e "\n${BLUE}=== INTERACTIVE SMB SHELL ===${NC}"
        echo "Available hosts:"

        for i in "${!hosts[@]}"; do
            echo "$((i+1))) ${hosts[i]}"
        done

        echo "0) Return to main menu"
        echo -e "${YELLOW}Select a host or enter an IP manually:${NC}"
        read -r selection

        if [ "$selection" = "0" ]; then
            echo "Returning to main menu..."
            break
        fi

        if [[ "$selection" =~ ^[0-9]+$ ]] && [ "$selection" -gt 0 ] && [ "$selection" -le ${#hosts[@]} ]; then
            selected_host="${hosts[$((selection-1))]}"
        elif [[ "$selection" =~ ^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$ ]]; then
            selected_host="$selection"
        else
            echo -e "${RED}Invalid selection${NC}"
            continue
        fi

        execute_smb_shell "$selected_host"
    done
}

# Function to scan SMB resources
scan_smb() {
    echo -e "${BLUE}=== SMB Resources ===${NC}"
    local smb_hosts=()
    truncate -s 0 "$TEMP_FILE"
    nmap -n -p 445 --open -e "$IFACE" "$NETWORK" 2>/dev/null |
    awk '/Nmap scan report/{ip=$NF}/445\/tcp open/{print ip}' | while read -r ip; do
        echo "Shared resources on $ip:"; timeout 10 smbclient -L "//$ip" -N 2>/dev/null || echo "  Could not access"
        echo ""
        echo "$ip" >> "$TEMP_FILE"
    done

    # Read IPs from temp file
    if [ -f "$TEMP_FILE" ]; then
        mapfile -t smb_hosts < "$TEMP_FILE"
    fi

    # If hosts with SMB were found, ask for interactive shell
    if [ ${#smb_hosts[@]} -gt 0 ]; then
        echo -e "\n${GREEN}Found ${#smb_hosts[@]} host(s) with SMB open${NC}"
        echo -e "${YELLOW}Do you want to open an interactive smbclient shell? (y/n):${NC}"
        read -r response

        case "$response" in
            [yY]|[yY][eE][sS])
                interactive_smb_shell "${smb_hosts[@]}"
                ;;
            *)
                echo "Continuing with main menu..."
                ;;
        esac
    else
        echo -e "${RED}No hosts with SMB open found${NC}"
    fi

    echo ""
}

# Cleanup function
cleanup() {
    rm -f "$TEMP_FILE"
    [ -n "$WPA_PID" ] && kill -TERM "$WPA_PID" 2>/dev/null && wait "$WPA_PID" 2>/dev/null
    [ -f "$DHCP_PIDFILE" ] && dhclient -r -pf "$DHCP_PIDFILE" "$IFACE" 2>/dev/null || true
    [ -f "$DHCP_PIDFILE" ] && kill -TERM "$(cat "$DHCP_PIDFILE")" 2>/dev/null || true

    restore_addrs
}

trap cleanup EXIT

# Verify root privileges
if [ "$EUID" -ne 0 ]; then
    echo "Dark Recon - ${RED}Error:${NC} This script must be run with administrator privileges"
    exit 1
fi

# Verify arguments
if [ $# -lt 3 ]; then
    echo "Dark Recon - Usage: $0 <SSID> <PASSWORD> <INTERFACE> [option]"
    echo "Options: --list | --smb | --all"
    exit 1
fi

for cmd in nmap smbclient ip awk grep dhclient; do check_dep "$cmd"; done

SSID="$1"; PASSWORD="$2"; IFACE="$3"; OPTION="$4"

TEMP_FILE=$(mktemp -p /tmp)
chmod 600 "$TEMP_FILE"

# Save original interface configuration
mapfile -t ORIG_IPV4 < <(ip -4 -o addr show dev "$IFACE" | awk '{print $4}')
had_ip="0"; ((${#ORIG_IPV4[@]})) && had_ip="1"

# WiFi connection
wpa_passphrase "$SSID" "$PASSWORD" > "$TEMP_FILE"
echo -e "${BLUE}Connecting to $SSID...${NC}"
if ! wpa_supplicant -B -i "$IFACE" -c "$TEMP_FILE" >/dev/null 2>&1; then
    echo -e "${RED}Error:${NC} Could not connect to $SSID"; exit 1
fi

# Get PID of wpa_supplicant specific to this interface
WPA_PID=$(pgrep -f "wpa_supplicant.*-i $IFACE")

sleep 3

DHCP_PIDFILE="/tmp/dhclient.$IFACE.pid"
if ! timeout 15 dhclient -1 -pf "$DHCP_PIDFILE" "$IFACE" >/dev/null 2>&1; then
  echo -e "${RED}Error:${NC} Could not obtain IP address (timeout)"
  exit 1
fi

echo -e "${GREEN}Connected successfully${NC}"

# Get network segment
NETWORK=$(ip -4 route show dev "$IFACE" | awk '/proto kernel/ {print $1; exit}')
if [ -z "${NETWORK:-}" ]; then
    NETWORK=$(ip -4 -o addr show dev "$IFACE" | awk '{print $4; exit}')
fi

if [ -z "${NETWORK:-}" ]; then
    echo -e "${RED}Error:${NC} Could not determine network segment"
    exit 1
fi

echo -e "Detected network segment: ${YELLOW}$NETWORK${NC}"

# Main menu
if [ -n "$OPTION" ]; then
    case "$OPTION" in
        --list) list_devices ;;
        --smb) scan_smb ;;
        --all) list_devices; scan_smb ;;
        *) echo "Invalid option" ;;
    esac
    exit 0
fi

show_menu() {
    echo "==========================="
    echo "    DARK RECON v1.0"
    echo "  Network Intelligence"
    echo "==========================="
    echo "Network: $NETWORK"
    echo "==========================="
    echo "1) List all devices"
    echo "2) Search for SMB shared resources"
    echo "3) Execute all"
    echo "0) Exit"
    echo "==========================="
    echo -n "Select an option: "
}

# Main menu loop
while true; do
    show_menu; read -r opt
    case $opt in
        1) list_devices ;;
        2) scan_smb ;;
        3) list_devices; scan_smb ;;
        0) break ;;
        *) echo "Invalid option" ;;
    esac
    read -p "Press Enter to continue..." -r
done

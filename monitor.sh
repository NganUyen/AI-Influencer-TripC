#!/bin/bash

##############################################################################
# System and Docker Container Monitoring Script
# For AI Influencer Factory on AWS EC2
#
# Usage: ./monitor.sh [--continuous] [--interval SECONDS]
##############################################################################

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
CONTINUOUS=false
INTERVAL=5
COMPOSE_FILE="docker-compose.production.yml"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --continuous|-c)
            CONTINUOUS=true
            shift
            ;;
        --interval|-i)
            INTERVAL="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--continuous] [--interval SECONDS]"
            exit 1
            ;;
    esac
done

# Function to print section header
print_header() {
    echo -e "\n${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}$1${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

# Function to get status color
get_status_color() {
    if [ "$1" = "running" ] || [ "$1" = "healthy" ]; then
        echo "${GREEN}"
    elif [ "$1" = "starting" ]; then
        echo "${YELLOW}"
    else
        echo "${RED}"
    fi
}

# Function to check if value exceeds threshold
check_threshold() {
    local value=$1
    local warning=$2
    local critical=$3
    
    if (( $(echo "$value >= $critical" | bc -l) )); then
        echo "${RED}"
    elif (( $(echo "$value >= $warning" | bc -l) )); then
        echo "${YELLOW}"
    else
        echo "${GREEN}"
    fi
}

# Function to display system resources
show_system_resources() {
    print_header "📊 System Resources"
    
    # CPU Usage
    cpu_usage=$(top -bn1 | grep "Cpu(s)" | sed "s/.*, *\([0-9.]*\)%* id.*/\1/" | awk '{print 100 - $1}')
    cpu_color=$(check_threshold "$cpu_usage" 70 85)
    echo -e "${cpu_color}CPU Usage:${NC}     ${cpu_color}${cpu_usage}%${NC}"
    
    # Memory Usage
    mem_info=$(free -m | awk 'NR==2{printf "%.2f %.2f %.2f", $3*100/$2, $3, $2}')
    mem_percent=$(echo $mem_info | awk '{print $1}')
    mem_used=$(echo $mem_info | awk '{print $2}')
    mem_total=$(echo $mem_info | awk '{print $3}')
    mem_color=$(check_threshold "$mem_percent" 80 90)
    echo -e "${mem_color}Memory Usage:${NC}   ${mem_color}${mem_percent}%${NC} (${mem_used}MB / ${mem_total}MB)"
    
    # Swap Usage
    swap_info=$(free -m | awk 'NR==3{printf "%.2f %.2f %.2f", ($2>0?$3*100/$2:0), $3, $2}')
    swap_percent=$(echo $swap_info | awk '{print $1}')
    swap_used=$(echo $swap_info | awk '{print $2}')
    swap_total=$(echo $swap_info | awk '{print $3}')
    swap_color=$(check_threshold "$swap_percent" 40 60)
    echo -e "${swap_color}Swap Usage:${NC}    ${swap_color}${swap_percent}%${NC} (${swap_used}MB / ${swap_total}MB)"
    
    # Disk Usage
    disk_info=$(df -h / | awk 'NR==2{printf "%s %s %s", $5, $3, $2}' | sed 's/%//')
    disk_percent=$(echo $disk_info | awk '{print $1}')
    disk_used=$(echo $disk_info | awk '{print $2}')
    disk_total=$(echo $disk_info | awk '{print $3}')
    disk_color=$(check_threshold "$disk_percent" 80 90)
    echo -e "${disk_color}Disk Usage:${NC}    ${disk_color}${disk_percent}%${NC} (${disk_used} / ${disk_total})"
    
    # Load Average
    load_avg=$(uptime | awk -F'load average:' '{print $2}' | xargs)
    echo -e "${BLUE}Load Average:${NC}  ${load_avg}"
    
    # Uptime
    uptime_info=$(uptime -p | sed 's/up //')
    echo -e "${BLUE}Uptime:${NC}        ${uptime_info}"
}

# Function to display Docker containers
show_docker_containers() {
    print_header "🐳 Docker Containers"
    
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}Docker is not installed or not in PATH${NC}"
        return
    fi
    
    # Check if compose file exists
    if [ ! -f "$COMPOSE_FILE" ]; then
        echo -e "${YELLOW}Compose file not found: $COMPOSE_FILE${NC}"
        echo "Showing all running containers instead..."
        docker ps --format "table {{.Names}}\t{{.Status}}\t{{.CPUPerc}}\t{{.MemPerc}}\t{{.NetIO}}"
        return
    fi
    
    # Get container stats
    printf "%-30s %-15s %-10s %-10s %-20s\n" "CONTAINER" "STATUS" "CPU" "MEMORY" "NET I/O"
    echo "───────────────────────────────────────────────────────────────────────────────"
    
    # Get list of services
    services=$(docker compose -f "$COMPOSE_FILE" ps --services 2>/dev/null)
    
    if [ -z "$services" ]; then
        echo -e "${YELLOW}No services found or containers not running${NC}"
        return
    fi
    
    while IFS= read -r service; do
        container_name=$(docker compose -f "$COMPOSE_FILE" ps -q "$service" 2>/dev/null | head -1)
        
        if [ -z "$container_name" ]; then
            continue
        fi
        
        # Get container stats (sample for 1 second)
        stats=$(docker stats "$container_name" --no-stream --format "{{.Container}}\t{{.Status}}\t{{.CPUPerc}}\t{{.MemPerc}}\t{{.NetIO}}" 2>/dev/null | tail -1)
        
        if [ -z "$stats" ]; then
            printf "%-30s ${RED}%-15s${NC}\n" "$service" "NOT RUNNING"
            continue
        fi
        
        container=$(echo "$stats" | awk '{print $1}')
        status=$(docker inspect --format='{{.State.Status}}' "$container_name" 2>/dev/null)
        cpu=$(echo "$stats" | awk '{print $3}')
        mem=$(echo "$stats" | awk '{print $4}')
        net=$(echo "$stats" | awk '{print $5" "$6}')
        
        # Get health status if available
        health=$(docker inspect --format='{{.State.Health.Status}}' "$container_name" 2>/dev/null)
        if [ -z "$health" ] || [ "$health" = "<no value>" ]; then
            health=""
        else
            health=" [$health]"
        fi
        
        status_color=$(get_status_color "$status")
        
        # Color code CPU and memory
        cpu_value=$(echo $cpu | sed 's/%//')
        mem_value=$(echo $mem | sed 's/%//')
        cpu_color=$(check_threshold "$cpu_value" 70 90)
        mem_color=$(check_threshold "$mem_value" 80 90)
        
        printf "%-30s ${status_color}%-15s${NC} ${cpu_color}%-10s${NC} ${mem_color}%-10s${NC} %-20s\n" \
            "$service" "${status}${health}" "$cpu" "$mem" "$net"
    done <<< "$services"
}

# Function to show service-specific insights
show_service_insights() {
    print_header "🔍 Service Insights"
    
    # Temporal health
    if docker compose -f "$COMPOSE_FILE" ps | grep -q "temporal.*running"; then
        temporal_health=$(curl -s http://localhost:8080/api/v1/health 2>/dev/null)
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}✓${NC} Temporal Server: Online"
        else
            echo -e "${RED}✗${NC} Temporal Server: UI not responding"
        fi
    fi
    
    # Backend health
    if docker compose -f "$COMPOSE_FILE" ps | grep -q "backend.*running"; then
        backend_health=$(curl -s http://localhost:8000/health 2>/dev/null)
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}✓${NC} Backend API: $(echo $backend_health | grep -o '"status":"[^"]*"' | cut -d'"' -f4)"
        else
            echo -e "${RED}✗${NC} Backend API: Not responding"
        fi
    fi
    
    # PostgreSQL connections
    if docker compose -f "$COMPOSE_FILE" ps | grep -q "postgres.*running"; then
        pg_connections=$(docker exec ai-influencer-postgres psql -U postgres -t -c "SELECT count(*) FROM pg_stat_activity;" 2>/dev/null | xargs)
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}✓${NC} PostgreSQL: $pg_connections active connections"
        else
            echo -e "${YELLOW}⚠${NC} PostgreSQL: Cannot query connection count"
        fi
    fi
    
    # Redis info
    if docker compose -f "$COMPOSE_FILE" ps | grep -q "redis.*running"; then
        redis_keys=$(docker exec ai-influencer-redis redis-cli DBSIZE 2>/dev/null | grep -o '[0-9]*')
        redis_mem=$(docker exec ai-influencer-redis redis-cli INFO memory 2>/dev/null | grep "used_memory_human" | cut -d':' -f2 | tr -d '\r')
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}✓${NC} Redis: $redis_keys keys, $redis_mem used"
        else
            echo -e "${YELLOW}⚠${NC} Redis: Cannot query info"
        fi
    fi
}

# Function to show recent errors
show_recent_errors() {
    print_header "⚠️  Recent Errors (Last 50 lines)"
    
    if [ ! -f "$COMPOSE_FILE" ]; then
        echo -e "${YELLOW}Compose file not found${NC}"
        return
    fi
    
    errors=$(docker compose -f "$COMPOSE_FILE" logs --tail=50 2>/dev/null | grep -i "error\|exception\|failed\|fatal" | tail -10)
    
    if [ -z "$errors" ]; then
        echo -e "${GREEN}No recent errors found${NC}"
    else
        echo "$errors" | while IFS= read -r line; do
            echo -e "${RED}$line${NC}"
        done
    fi
}

# Function to show network statistics
show_network_stats() {
    print_header "🌐 Network Statistics"
    
    # Active connections
    established=$(netstat -an 2>/dev/null | grep ESTABLISHED | wc -l)
    echo -e "${BLUE}Active Connections:${NC} $established"
    
    # Listen ports
    listening=$(netstat -tln 2>/dev/null | grep LISTEN | wc -l)
    echo -e "${BLUE}Listening Ports:${NC}    $listening"
    
    # Top connections by IP
    echo -e "\n${BLUE}Top 5 Connection Sources:${NC}"
    netstat -an 2>/dev/null | grep ESTABLISHED | awk '{print $5}' | cut -d: -f1 | sort | uniq -c | sort -rn | head -5
}

# Main monitoring function
run_monitor() {
    clear
    echo -e "${MAGENTA}"
    echo "╔════════════════════════════════════════════════════════════════╗"
    echo "║          AI INFLUENCER FACTORY - SYSTEM MONITOR                ║"
    echo "║                    $(date '+%Y-%m-%d %H:%M:%S')                    ║"
    echo "╚════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    
    show_system_resources
    show_docker_containers
    show_service_insights
    show_network_stats
    show_recent_errors
    
    if [ "$CONTINUOUS" = true ]; then
        echo -e "\n${CYAN}Refreshing in ${INTERVAL} seconds... (Press Ctrl+C to stop)${NC}"
    fi
}

# Main execution
if [ "$CONTINUOUS" = true ]; then
    while true; do
        run_monitor
        sleep "$INTERVAL"
    done
else
    run_monitor
    echo -e "\n${CYAN}Tip: Use --continuous flag for real-time monitoring${NC}"
fi

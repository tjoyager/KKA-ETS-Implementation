#!/usr/bin/env bash
set -euo pipefail

# Subcommands for testing or debugging without cloning
if [[ "${1:-}" == "test" ]]; then
    shift
    export KKA_DISABLE_AUDIO="${KKA_DISABLE_AUDIO:-1}"
    export LIBGL_ALWAYS_SOFTWARE="${LIBGL_ALWAYS_SOFTWARE:-1}"
    for t in tests/test_full_suite.py tests/test_phase3_integration.py tests/test_phase4_integration.py; do
        echo ">>> Running $t"
        python -c "import runpy; from ursina import Ursina; Ursina(window_type='none'); runpy.run_path('$t', run_name='__main__')"
    done
    exit 0
elif [[ "${1:-}" == "bash" || "${1:-}" == "sh" ]]; then
    exec "$@"
fi

# Determine display mode:
# - "x11" if SIM_MODE=x11, or if user mounted host X11 socket and passed DISPLAY
# - "browser" (Xvfb + x11vnc + noVNC on :6080) by default so it works on Windows/macOS/Linux
MODE="${SIM_MODE:-auto}"
if [[ "$MODE" == "auto" ]]; then
    raw_disp="${DISPLAY:-}"
    disp_num="${raw_disp#*:}"
    disp_num="${disp_num%%.*}"
    if [[ -n "${raw_disp}" && -n "${disp_num}" && -S "/tmp/.X11-unix/X${disp_num}" ]]; then
        MODE="x11"
    else
        MODE="browser"
    fi
fi

# Use Mesa software OpenGL automatically when no DRI GPU device is passed
if [[ ! -d /dev/dri ]]; then
    export LIBGL_ALWAYS_SOFTWARE="${LIBGL_ALWAYS_SOFTWARE:-1}"
fi
export KKA_DISABLE_AUDIO="${KKA_DISABLE_AUDIO:-1}"

if [[ "$MODE" == "x11" ]]; then
    echo "[kka-sim] Starting in native X11 mode (DISPLAY=${DISPLAY})..."
    exec python main.py "$@"
fi

# Browser / noVNC mode
DISPLAY_NUM="${DISPLAY_NUM:-99}"
export DISPLAY=":${DISPLAY_NUM}"
SCREEN_RES="${SCREEN_RESOLUTION:-1366x768x24}"
NOVNC_PORT="${NOVNC_PORT:-${PORT:-6080}}"
VNC_PORT="${VNC_PORT:-5900}"

PIDS=()
APP_PID=""
cleanup() {
    trap - EXIT INT TERM
    if [[ -n "${APP_PID}" ]]; then
        kill -TERM "${APP_PID}" 2>/dev/null || true
    fi
    for pid in "${PIDS[@]:-}"; do
        kill -TERM "$pid" 2>/dev/null || true
    done
    sleep 0.2
    if [[ -n "${APP_PID}" ]]; then
        kill -KILL "${APP_PID}" 2>/dev/null || true
    fi
    for pid in "${PIDS[@]:-}"; do
        kill -KILL "$pid" 2>/dev/null || true
    done
}
trap 'cleanup; exit 0' INT TERM
trap cleanup EXIT

echo "[kka-sim] Starting virtual X11 display (${DISPLAY} @ ${SCREEN_RES})..."
Xvfb "${DISPLAY}" -screen 0 "${SCREEN_RES}" -ac +extension GLX +render -noreset >/tmp/xvfb.log 2>&1 &
PIDS+=($!)

for _ in $(seq 1 30); do
    if [[ -S "/tmp/.X11-unix/X${DISPLAY_NUM}" ]]; then
        break
    fi
    sleep 0.2
done

fluxbox >/tmp/fluxbox.log 2>&1 &
PIDS+=($!)

VNC_AUTH_ARGS=(-nopw)
if [[ -n "${VNC_PASSWORD:-}" ]]; then
    mkdir -p /root/.vnc
    x11vnc -storepasswd "${VNC_PASSWORD}" /root/.vnc/passwd >/dev/null 2>&1
    VNC_AUTH_ARGS=(-rfbauth /root/.vnc/passwd)
fi

x11vnc -display "${DISPLAY}" -forever -shared -rfbport "${VNC_PORT}" "${VNC_AUTH_ARGS[@]}" -quiet >/tmp/x11vnc.log 2>&1 &
PIDS+=($!)

websockify --web=/usr/share/novnc "${NOVNC_PORT}" "localhost:${VNC_PORT}" >/tmp/novnc.log 2>&1 &
PIDS+=($!)

if [[ "${PUBLIC_TUNNEL:-0}" =~ ^(1|true|yes)$ ]]; then
    echo "[kka-sim] Starting Cloudflare Quick Tunnel (no host install needed)..."
    for _ in $(seq 1 20); do
        if python -c "import socket; s=socket.create_connection(('127.0.0.1', ${NOVNC_PORT}), 0.5); s.close()" 2>/dev/null; then
            break
        fi
        sleep 0.25
    done

    cloudflared tunnel --no-autoupdate --url "http://localhost:${NOVNC_PORT}" >/tmp/cloudflared.log 2>&1 &
    PIDS+=($!)

    PUBLIC_URL=""
    for _ in $(seq 1 40); do
        PUBLIC_URL=$(grep -oE 'https://[a-zA-Z0-9-]+\.trycloudflare\.com' /tmp/cloudflared.log | head -n 1 || true)
        if [[ -n "${PUBLIC_URL}" ]]; then
            break
        fi
        sleep 0.5
    done

    echo "======================================================================"
    echo " KKA 3D Warehouse AGV Simulator is running!"
    if [[ -n "${PUBLIC_URL}" ]]; then
        echo " Public URL (any network): ${PUBLIC_URL}"
    else
        echo " Public URL pending — inspect logs: cat /tmp/cloudflared.log"
    fi
    echo " Local Browser URL       : http://localhost:${NOVNC_PORT}/"
    if [[ -z "${VNC_PASSWORD:-}" ]]; then
        echo " WARNING: VNC_PASSWORD is not set! Pass -e VNC_PASSWORD=... for security."
    fi
    echo " Press Ctrl+C (or run 'docker stop') to exit cleanly."
    echo "======================================================================"
else
    echo "======================================================================"
    echo " KKA 3D Warehouse AGV Simulator is running in browser mode!"
    echo " Open in your browser: http://localhost:${NOVNC_PORT}/"
    echo " Press Ctrl+C (or run 'docker stop') to exit cleanly."
    echo "======================================================================"
fi

python main.py "$@" &
APP_PID=$!
wait "${APP_PID}"

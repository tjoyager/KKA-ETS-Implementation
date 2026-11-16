FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app \
    KKA_DISABLE_AUDIO=1 \
    SCREEN_RESOLUTION=1366x768x24 \
    KKA_WINDOW_SIZE=1280x720

WORKDIR /app

# Install Mesa OpenGL, X11 libs for Panda3D/Ursina, plus Xvfb + fluxbox + x11vnc + noVNC
# so the 3D simulator runs out-of-the-box in any web browser or native X11 session.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libgl1-mesa-dri \
    libglu1-mesa \
    libegl1 \
    libfreetype6 \
    libx11-6 \
    libxext6 \
    libxrender1 \
    libxrandr2 \
    libxi6 \
    libxcursor1 \
    libxinerama1 \
    libxxf86vm1 \
    xvfb \
    xauth \
    fluxbox \
    x11vnc \
    novnc \
    websockify \
    procps \
    tini \
    && rm -rf /var/lib/apt/lists/*

# Redirect root http://localhost:6080/ straight into auto-connecting scaled noVNC canvas
RUN printf '%s\n' \
    '<!DOCTYPE html>' \
    '<html><head><meta http-equiv="refresh" content="0; url=/vnc.html?autoconnect=true&resize=scale"></head>' \
    '<body><a href="/vnc.html?autoconnect=true&resize=scale">Open KKA 3D Simulator</a></body></html>' \
    > /usr/share/novnc/index.html

COPY requirements.txt pyproject.toml README.md main.py ./
COPY src/ ./src/
COPY assets/ ./assets/
COPY tests/ ./tests/

RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY --from=cloudflare/cloudflared:latest /usr/local/bin/cloudflared /usr/local/bin/cloudflared
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

EXPOSE 6080 5900

ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/entrypoint.sh"]

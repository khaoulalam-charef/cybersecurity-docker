# Image de base combinant Python et Node.js
FROM python:3.11-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends curl tini nodejs npm && \
    rm -rf /var/lib/apt/lists/*

RUN npm install -g nodemon

# --- NOUVEAU : créer un utilisateur non-root ---
RUN useradd -m -u 10001 appuser

WORKDIR /usr/local/app

COPY vote/requirements.txt ./vote/requirements.txt
RUN pip install --no-cache-dir -r ./vote/requirements.txt && pip install watchdog

COPY result/package*.json ./result/
RUN cd result && npm ci && npm cache clean --force

COPY vote/ ./vote
COPY result/ ./result

ENV FLASK_ENV=development
ENV PORT=4000

EXPOSE 5000
EXPOSE 4000

RUN echo '#!/bin/sh\n\
# Lancement de Vote (Python) sur le port 5000\n\
cd /usr/local/app/vote && gunicorn app:app -b 0.0.0.0:5000 --log-file - --access-logfile - &\n\
# Lancement de Result (Node.js) sur le port 4000\n\
cd /usr/local/app/result && exec nodemon --inspect=0.0.0.0 server.js\n\
' > /usr/local/app/start.sh

RUN chmod +x /usr/local/app/start.sh

# --- NOUVEAU : donner la propriété des fichiers à appuser avant de basculer ---
RUN chown -R appuser:appuser /usr/local/app

# --- NOUVEAU : basculer en non-root avant le démarrage ---
USER appuser

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["/usr/local/app/start.sh"]
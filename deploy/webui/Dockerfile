FROM php:8.2-apache

# Settings web UI for the voice-trigger stack.
# Writes ../secrets/.env (read by the Python app). No secrets in code.
# Ships docker-cli so it can restart/reload the app service and read its logs.

WORKDIR /var/www/html

# Install docker-cli (static binary) so PHP can call `docker compose`.
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates && \
    curl -fsSL https://download.docker.com/linux/static/stable/x86_64/docker-27.3.1.tgz -o /tmp/docker.tgz && \
    tar -xzf /tmp/docker.tgz -C /tmp && \
    mv /tmp/docker/docker /usr/local/bin/docker && \
    rm -rf /tmp/docker /tmp/docker.tgz && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Mount the host docker socket at runtime (see compose volumes) so the
# CLI controls the same daemon that runs the stack.

COPY . /var/www/html/

# Block web access to the secrets directory.
RUN echo "Require all denied" > /var/www/html/secrets/.htaccess

EXPOSE 80
CMD ["apache2-foreground"]

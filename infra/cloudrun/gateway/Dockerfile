# Gateway for Google Cloud Run: same Traefik version and rules as docker-compose, but the
# three services are reached at their Cloud Run addresses instead of through Docker.
FROM traefik:v3.2

COPY traefik.yml /etc/traefik/traefik.yml
COPY dynamic.yml /etc/traefik/dynamic.yml

# Cloud Run sends traffic to the port in $PORT (8080 by default).
EXPOSE 8080

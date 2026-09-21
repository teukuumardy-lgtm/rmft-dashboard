FROM node:20-alpine AS build
WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .
# In docker-compose, the frontend calls the backend via same-origin /api,
# proxied by nginx.conf to the "backend" container on Docker's internal
# network — no VITE_API_BASE_URL needed there. On a host where frontend and
# backend are deployed as separate services with separate public URLs (e.g.
# Railway, Render), pass the backend's public URL as a build arg instead —
# Vite bakes VITE_* into the JS bundle at build time, so this must be set
# BEFORE this RUN step, not as a runtime-only env var.
ARG VITE_API_BASE_URL=""
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
# Rendered into /etc/nginx/conf.d/default.conf at container startup by the
# base image's built-in envsubst-on-templates entrypoint, substituting
# ${PORT} — see nginx.conf.template for why (Render and similar hosts inject
# a dynamic PORT; a hardcoded "listen 80" would fail their port detection).
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
ENV PORT=80
EXPOSE 80

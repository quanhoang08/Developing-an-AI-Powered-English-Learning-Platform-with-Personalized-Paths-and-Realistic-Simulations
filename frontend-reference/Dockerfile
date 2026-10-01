FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
# "/" = gọi API cùng origin (Caddy chuyển /api sang backend).
ENV VITE_BACKEND_URL=/
RUN npx vite build

FROM caddy:2-alpine
COPY Caddyfile /etc/caddy/Caddyfile
COPY --from=build /app/dist /srv

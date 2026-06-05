# Build stage
FROM node:18-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
# We must ensure the frontend knows where the backend is.
# Vite loads .env variables, so we will inject the VITE_API_BASE_URL if needed.
# But for simplicity, we assume the frontend code handles it or accesses /api relatively.
RUN npm run build

# Serve stage
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
# Replace default nginx config to route /api to backend 8088
RUN echo 'server { \
    listen 8081; \
    client_max_body_size 50M; \
    location / { \
        root /usr/share/nginx/html; \
        index index.html index.htm; \
        try_files $uri $uri/ /index.html; \
    } \
    location /api/ { \
        proxy_pass http://localhost:8088/api/; \
        proxy_read_timeout 300s; \
        proxy_connect_timeout 300s; \
    } \
}' > /etc/nginx/conf.d/default.conf

EXPOSE 8081
CMD ["nginx", "-g", "daemon off;"]

# 1. Compilar la app
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
# Token público de Mapbox (viene del .env de la raíz a través de docker-compose)
ARG MAPBOX_API_KEY=""
ENV MAPBOX_API_KEY=$MAPBOX_API_KEY
RUN npm run build

# 2. Servirla con nginx
FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80

FROM node:20-alpine AS build

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM nginx:1.27-alpine

# BACKEND_URL is substituted into the config by nginx's own docker-entrypoint
# (via envsubst on any *.template file) before the server starts - this is
# what lets the same image proxy /api to a Docker Compose service name
# locally (http://backend:8000) and to a real backend URL when deployed
# somewhere the two aren't on the same private network (e.g. Render).
ENV BACKEND_URL=http://backend:8000
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]

FROM node:25-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm run build

FROM alpine:3.24 AS exercise-images
ARG FREE_EXERCISE_DB=f00c92c7dcf1216a928a52c3706c7ce8e2f71ed5
RUN wget -qO- "https://github.com/yuhonas/free-exercise-db/archive/${FREE_EXERCISE_DB}.tar.gz" \
    | tar -xz -C /tmp "free-exercise-db-${FREE_EXERCISE_DB}/exercises" \
    && mv "/tmp/free-exercise-db-${FREE_EXERCISE_DB}/exercises" /exercise-img

FROM nginxinc/nginx-unprivileged:1.31-alpine
USER root
RUN apk upgrade --no-cache
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=exercise-images /exercise-img /usr/share/nginx/html/exercise-img
COPY --from=build /app/dist /usr/share/nginx/html
USER 101

# Dockerfile para desenvolvimento com hot reload
FROM node:18-alpine

WORKDIR /app

COPY package*.json ./
RUN npm ci --silent

COPY . .

ENV REACT_APP_API_URL=http://localhost:8000
ENV REACT_APP_WS_URL=ws://localhost:8000

EXPOSE 3000

CMD ["npm", "start"]

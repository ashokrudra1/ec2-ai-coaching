# Stage 1: Building the code
FROM node:22-alpine AS builder

WORKDIR /app

COPY frontend/package*.json ./
RUN npm install

COPY frontend/ ./
RUN npm run build

# Stage 2: Run the built code
FROM node:22-alpine

WORKDIR /app

ENV NODE_ENV production

COPY --from=builder /app/ ./

EXPOSE 3000

CMD ["npm", "start"]

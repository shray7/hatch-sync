FROM node:20-slim

WORKDIR /app

COPY package.json ./
RUN npm install --omit=dev

COPY index.js ./

ENV PORT=3020
ENV COMPANION_DATADIR=/tmp/companion
RUN mkdir -p /tmp/companion
EXPOSE 3020

CMD ["node", "index.js"]

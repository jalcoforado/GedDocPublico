FROM mcr.microsoft.com/playwright:v1.49.0-noble

WORKDIR /e2e

COPY package.json ./
RUN npm install --no-audit --no-fund

COPY . .

CMD ["npx", "playwright", "test"]

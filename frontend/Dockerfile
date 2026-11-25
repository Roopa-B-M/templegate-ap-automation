# TempleGate AP Automation - frontend (React 18 + Vite dev server)
FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install --no-audit --no-fund

COPY . .

EXPOSE 5173

# Dev server proxies /api and /media to the backend service (see vite.config.js).
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

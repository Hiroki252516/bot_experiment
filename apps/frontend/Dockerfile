FROM node:22-alpine

WORKDIR /app/apps/frontend

COPY apps/frontend/package.json apps/frontend/package-lock.json* ./
RUN npm install

COPY apps/frontend /app/apps/frontend
COPY packages/shared-schemas /app/packages/shared-schemas

RUN npm run build

EXPOSE 3000

CMD ["npm", "run", "start"]


FROM node:20-alpine

WORKDIR /app

# Copy dependency specifications
COPY package.json package-lock.json ./

# Install dependencies for container platform
RUN npm install

# Copy application source code
COPY . .

# Expose Vite development server port
EXPOSE 5173

ENV HOST=0.0.0.0
ENV PORT=5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]

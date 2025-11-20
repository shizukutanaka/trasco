FROM node:20-slim

WORKDIR /app

# Copy package files
COPY package.json package-lock.json ./
RUN npm install

# Copy application
COPY . .

# Expose port
EXPOSE 3000

# Run the application
CMD ["npm", "start"]

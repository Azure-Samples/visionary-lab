# Use Node.js 19 as the base image for development
FROM node:19-alpine

# Set working directory
WORKDIR /app

# Install dependencies needed for node-gyp
RUN apk add --no-cache libc6-compat

# Copy package files
COPY package.json package-lock.json ./

# Install dependencies
RUN npm ci

# Copy the rest of the application code
COPY . .

# Set default environment variables
ENV NEXT_TELEMETRY_DISABLED=1
ENV API_HOSTNAME=localhost
ENV API_PORT=8000
ENV API_PROTOCOL=http
ENV STORAGE_ACCOUNT_NAME=devstoreaccount1

# Expose the port the app will run on
EXPOSE 3000

# Start the development server
CMD ["npm", "run", "dev"]

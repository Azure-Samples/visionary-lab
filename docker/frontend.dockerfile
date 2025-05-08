# # # # # FROM node:20-alpine as builder
# # # # # WORKDIR /app

# # # # # COPY /frontend /app

# # # # # RUN ["npm", "install", "--legacy-peer-deps"]
# # # # # CMD ["npm", "run" , "dev"]


# # FROM node:20-alpine as base
# # FROM base as builder
# # WORKDIR /app

# # # Copy dependency files
# # COPY frontend/package*.json ./
# # RUN npm install --legacy-peer-deps

# # # Copy and build
# # COPY /frontend /app
# # RUN npm run build

# # # Final lightweight image
# # FROM base
# # WORKDIR /app
# # ENV NODE_ENV=production

# # COPY --from=builder /app/.next ./.next
# # COPY --from=builder /app/package.json ./package.json
# # COPY --from=builder /app/node_modules ./node_modules
# # COPY --from=builder /app/public ./public

# # EXPOSE 3000
# # CMD ["npm", "run", "start"]


# Use Node.js 19 as the base image for development
FROM node:19-alpine

# Set working directory
WORKDIR /app

# Install dependencies needed for node-gyp
RUN apk add --no-cache libc6-compat

# Copy package files
COPY frontend/package.json frontend/package-lock.json ./

# Install dependencies
RUN npm ci

# Copy the rest of the application code
COPY ./frontend .

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
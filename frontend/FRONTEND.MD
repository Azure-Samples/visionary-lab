# Frontend Documentation

This document provides a factual overview of the frontend system for the AI Content Lab based on code examination.

## 1. Project Structure

The frontend is a Next.js application with the following key directories:

```
frontend/
├── .env.local               # Local environment variables
├── Dockerfile               # Container configuration
├── app/                     # Next.js App Router pages and layouts
│   ├── api/                 # API routes, including the trusted backend proxy
│   ├── auth/                # Authentication-related routes
│   ├── edit-image/          # Image editing functionality
│   ├── gallery/             # Gallery view for content
│   ├── jobs/                # Job management interface
│   ├── login/               # Login page
│   ├── new-image/           # Image creation page
│   ├── new-video/           # Video creation page
│   ├── settings/            # Application settings
│   ├── video/               # Video viewing functionality
│   ├── layout.tsx           # Root layout component
│   └── page.tsx             # Home page component
├── components/              # Reusable React components
│   ├── ui/                  # UI component library
│   ├── video/               # Video-specific components
│   ├── ImageCreationContainer.tsx 
│   ├── VideoCreationContainer.tsx
│   ├── ImageDetailView.tsx
│   ├── VideoDetailView.tsx
│   └── ...                  # Many other component files
├── context/                 # React context providers
├── hooks/                   # Custom React hooks
├── lib/                     # Utility libraries
├── public/                  # Static assets
├── services/                # API service integrations
│   ├── api.ts               # Backend API client
│   ├── imageService.ts      # Image-specific API functions
│   ├── imageJobs.ts         # Durable image-job HTTP client
│   └── sas-token.ts         # Azure storage SAS token management
├── types/                   # TypeScript type definitions
└── utils/                   # Utility functions
```

## 2. Technology Stack

The frontend is built with:

- **Next.js 16.3.1**: App Router architecture with React 19
- **TypeScript**: For type safety
- **Tailwind CSS**: For styling
- **NextAuth.js (next-auth v5)**: For authentication
- **Radix UI**: For accessible UI components
- **Framer Motion**: For animations
- **FFMPEG**: For client-side video processing

## 3. Key Features & Implementation Details

### Authentication

- Uses NextAuth.js with Microsoft Entra ID (formerly Azure AD) provider
- Authentication is defined in `auth.ts` with the following scopes:
  - `openid profile email User.Read`
- The auth system uses environment variables for configuration:
  - `AUTH_MICROSOFT_ENTRA_ID_ID`
  - `AUTH_MICROSOFT_ENTRA_ID_TENANT_ID`
  - `AUTH_MICROSOFT_ENTRA_ID_SECRET`
  - `AUTH_SECRET`

### API Communication

- Browser API calls use the same-origin `/api/backend/*` proxy. The backend Container App remains environment-internal; the proxy strips caller-supplied identity headers and forwards either the Easy Auth principal or a server-issued HttpOnly anonymous owner ID.
- Backend API is accessed via service modules in `services/` directory
- `api.ts` contains the core API client functionality with:
  - Configurable API URL via environment variables (`NEXT_PUBLIC_API_PROTOCOL`, `NEXT_PUBLIC_API_HOSTNAME`, `NEXT_PUBLIC_API_PORT`)
  - Browser URL: `/api/backend/api/v1`; server-side calls use the configured internal backend URL
  - Includes endpoints for image and video generation, editing, and management

### Content Generation UI

- **Image Creation**: Implemented in `ImageCreationContainer.tsx` and accessed via `/new-image`
- **Concurrent Image Jobs**: `image-jobs-context.tsx` persists optimistic submissions, reconciles monotonic job revisions, polls active/recent state independently, and centralizes cancel/retry actions.
- **Per-image Results**: Reserved output cards appear immediately in the target gallery and progressively become ready, failed, cancelled, or analyzed without blocking the composer.
- **Video Creation**: Implemented in `VideoCreationContainer.tsx` and accessed via `/new-video`
- **Image Editing**: Available at `/edit-image` route
- **Content Gallery**: Available at `/gallery` route

### Azure Storage Integration

- Configured to handle assets from Azure Blob Storage
- `next.config.ts` includes remotePatterns for Azure Blob Storage URLs
- SAS token management in `services/sas-token.ts` for secure access to blob storage

### Image Optimization

- Next.js Image component configured in `next.config.ts` for optimized image delivery
- Remote patterns include:
  - Backend API assets (`/api/v1/gallery/asset/**`)
  - Azure Blob Storage (`${STORAGE_ACCOUNT_NAME}.blob.core.windows.net`)

## 4. Environment Configuration

The frontend requires the following environment variables:

- **API Configuration**:
  - `NEXT_PUBLIC_API_PROTOCOL`: Protocol for backend API (http/https)
  - `NEXT_PUBLIC_API_HOSTNAME`: Hostname for backend API
  - `NEXT_PUBLIC_API_PORT`: Port for backend API
  
- **Azure Storage**:
  - `NEXT_PUBLIC_STORAGE_ACCOUNT_NAME`: Azure Storage account name

- **Authentication**:
  - `AUTH_MICROSOFT_ENTRA_ID_ID`: Microsoft Entra ID client ID
  - `AUTH_MICROSOFT_ENTRA_ID_TENANT_ID`: Microsoft Entra ID tenant ID
  - `AUTH_MICROSOFT_ENTRA_ID_SECRET`: Microsoft Entra ID client secret
  - `AUTH_SECRET`: Secret for NextAuth.js

## 5. Development

- The project uses modern Next.js development features:
  - Turbopack for faster development builds (`next dev --turbopack`)
  - Standalone output for optimized production deployment
  - ESLint for code quality enforcement

## 6. Component Architecture

- **UI Components**: Leverages Radix UI primitives for accessible UI components
- **Page Components**: Follows Next.js App Router pattern with:
  - Layout components for shared UI
  - Page components for route-specific content
  - Loading and error states
- **Container Components**: Complex UI logic encapsulated in container components
  - `ImageCreationContainer.tsx`
  - `VideoCreationContainer.tsx`
  - `ImageDetailView.tsx`
  - `VideoDetailView.tsx`

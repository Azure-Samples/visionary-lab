# Frontend Documentation

The frontend is a Next.js 15 application for generating, editing, organizing, and analyzing images.

## Project Structure

```text
frontend/
├── app/
│   ├── analyze/             # Custom image analysis
│   ├── api/                 # Next.js server routes
│   ├── edit-image/          # Image editing workflow
│   ├── login/               # Authentication page
│   ├── new-image/           # Image creation and gallery
│   ├── settings/            # Brand, analysis, and API settings
│   ├── layout.tsx           # Root application layout
│   └── page.tsx             # Home page
├── components/
│   ├── ui/                  # Shared UI primitives
│   ├── ImageCreationContainer.tsx
│   ├── ImageDetailView.tsx
│   ├── ImageOverlay.tsx
│   └── image-gallery-card.tsx
├── context/                 # Shared React state
├── hooks/                   # Custom React hooks
├── public/                  # Static application assets
├── services/
│   ├── api.ts               # Backend API client
│   ├── imageService.ts      # Image-specific API functions
│   └── sas-token.ts         # Image storage access
└── utils/                   # Gallery, image, and general helpers
```

## Technology Stack

- Next.js 15 with the App Router
- React 19 and TypeScript
- Tailwind CSS
- NextAuth.js with Microsoft Entra ID
- Radix UI primitives
- Framer Motion

## Main Workflows

- Create and browse images at `/new-image`.
- Edit existing images at `/edit-image`.
- Run custom image analysis at `/analyze`.
- Configure brand protection, analysis prompts, and API status at `/settings`.

The home route renders the image creation page.

## API and Storage

The client in `services/api.ts` uses `NEXT_PUBLIC_API_URL` when set. Otherwise it builds the backend URL from:

- `NEXT_PUBLIC_API_PROTOCOL`
- `NEXT_PUBLIC_API_HOSTNAME`
- `NEXT_PUBLIC_API_PORT`

Generated images are accessed from Azure Blob Storage. `services/sas-token.ts` obtains the image container URL and SAS token from the backend, while `next.config.ts` allows optimized image delivery from Azure-hosted URLs.

## Authentication

Authentication is configured in `auth.ts` with Microsoft Entra ID. Relevant environment variables are:

- `AUTH_MICROSOFT_ENTRA_ID_ID`
- `AUTH_MICROSOFT_ENTRA_ID_TENANT_ID`
- `AUTH_MICROSOFT_ENTRA_ID_SECRET`
- `AUTH_SECRET`

## Development

From `frontend/`:

```bash
npm install
npm run dev
```

Production verification uses `npm run build`.

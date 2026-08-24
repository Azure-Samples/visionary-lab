# Frontend Documentation

The frontend is a Next.js application for generating, editing, organizing, and analyzing images.

## Project Structure

```text
frontend/
├── app/
│   ├── analyze/             # Custom image analysis
│   ├── api/                 # Next.js routes, including the trusted backend proxy
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
│   ├── image-gallery-card.tsx
│   ├── image-job-output-card.tsx
│   └── image-jobs-activity.tsx
├── context/
│   ├── image-jobs-context.tsx
│   └── image-settings-context.tsx
├── public/                  # Static application assets and service worker
├── services/
│   ├── api.ts               # Image and gallery API client
│   ├── imageJobs.ts         # Durable image-job HTTP client
│   ├── imageService.ts      # Image-specific helpers
│   └── sas-token.ts         # Image storage access
├── types/
│   └── image-jobs.ts        # Image-job and output-slot contracts
└── utils/                   # Gallery, image, and general helpers
```

## Technology Stack

- Next.js with the App Router
- React and TypeScript
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

## Concurrent Image Generation

Text-to-image requests are submitted as durable backend jobs rather than being held open by the browser.

- `image-jobs-context.tsx` persists optimistic submissions, reconciles monotonic job revisions, polls active and recent jobs independently, and centralizes cancel and retry actions.
- Each requested image receives a reserved output card immediately in the target gallery.
- Output cards progressively move through queued, generating, saving, ready, failed, cancelled, and analysis states.
- Partial jobs retain successful outputs and can retry only their failed images.
- The composer snapshots and clears text prompts so another batch can be submitted while earlier batches continue.
- Image editing remains a blocking workflow because uploaded source files are still processed by the existing edit endpoint.

## API, Identity, and Storage

Browser API calls use the same-origin `/api/backend/api/v1` proxy. Server-side calls use the configured internal backend URL from `BACKEND_API_URL`, `NEXT_PUBLIC_API_URL`, or the protocol/hostname/port settings.

The proxy:

- strips caller-supplied owner and principal headers;
- forwards a trusted Easy Auth principal when available;
- otherwise uses a server-issued HttpOnly anonymous owner cookie;
- prevents browser and service-worker caching of user-specific API responses.

Generated images are accessed from Azure Blob Storage. `services/sas-token.ts` obtains the image container URL and SAS token from the backend, and ready job outputs use SAS-backed preview URLs before the gallery refresh completes.

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

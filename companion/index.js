require('dotenv').config()

const express = require('express')
const cors = require('cors')
const companion = require('@uppy/companion')

const app = express()

const PORT = process.env.PORT || 3020

const allowedOrigins = (process.env.COMPANION_CLIENT_ORIGINS || process.env.COMPANION_ALLOWED_ORIGINS || '').split(',').filter(Boolean)
const uploadUrls = (process.env.COMPANION_UPLOAD_URLS || '').split(',').filter(Boolean)
let uploadHeaders = {}
try {
  if (process.env.COMPANION_UPLOAD_HEADERS) {
    uploadHeaders = JSON.parse(process.env.COMPANION_UPLOAD_HEADERS)
  }
} catch (_) {}

const companionOptions = {
  providerOptions: {
    drive: {
      key: process.env.COMPANION_GOOGLE_KEY,
      secret: process.env.COMPANION_GOOGLE_SECRET
    }
  },
  server: {
    host: process.env.COMPANION_DOMAIN || 'localhost:' + PORT,
    protocol: process.env.COMPANION_PROTOCOL || 'http'
  },
  secret: process.env.COMPANION_SECRET || 'change-me-in-prod',
  filePath: process.env.COMPANION_DATADIR || './output',
  corsOrigins: allowedOrigins.length ? allowedOrigins : true,
  uploadUrls: uploadUrls.length ? uploadUrls : undefined,
  uploadHeaders: Object.keys(uploadHeaders).length ? uploadHeaders : undefined,
  enableGooglePickerEndpoint: process.env.COMPANION_ENABLE_GOOGLE_PICKER_ENDPOINT !== 'false',
  maxFilenameLength: parseInt(process.env.COMPANION_MAX_FILENAME_LENGTH || '500', 10) || 500,
  debug: process.env.NODE_ENV !== 'production'
}

// Health check and version (before Companion so not shadowed)
app.get('/healthz', (req, res) => res.json({ status: 'ok' }))
const companionPkg = require('@uppy/companion/package.json')
app.get('/version', (req, res) => res.json({
  companion: companionPkg.version,
  googlePicker: process.env.COMPANION_ENABLE_GOOGLE_PICKER_ENDPOINT !== 'false'
}))

// CORS for browser → Companion calls
app.use(cors({ origin: allowedOrigins.length ? allowedOrigins : false, credentials: true }))

const { app: companionApp } = companion.app(companionOptions)
app.use(companionApp)

const server = app.listen(PORT, () => {
  // eslint-disable-next-line no-console
  console.log(`Companion listening on ${PORT}`)
})

companion.socket(server, companionOptions)


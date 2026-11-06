// Preload for MCP servers that still fetch with node-fetch 2 (gaxios 6, so most
// Google client libraries). On Node 20 the default https agent keeps connections
// alive, and node-fetch 2 then fails reading a gzipped body with "Premature
// close": every OAuth token refresh fails while the server itself starts fine.
// Use it from a connector's env: NODE_OPTIONS: --require /app/node/no-keepalive.cjs
const https = require("https");
https.globalAgent = new https.Agent({ keepAlive: false });

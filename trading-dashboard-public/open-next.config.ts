import { defineCloudflareConfig } from "@opennextjs/cloudflare";

/**
 * Minimal OpenNext config for Cloudflare Pages.
 * SSR routes work out of the box; add R2/D1/DO bindings for caching if needed.
 */
export default defineCloudflareConfig({});

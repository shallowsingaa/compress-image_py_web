/**
 * Service Worker: APK Content-Type Fix
 *
 * Gitee CDN serves .apk files with Content-Type: application/zip,
 * causing mobile browsers to save them as .zip instead of .apk.
 *
 * This SW intercepts APK download requests, fetches the actual bytes
 * from Gitee, and re-serves them with the correct MIME type so that
 * mobile browsers recognize and save them as .apk.
 *
 * Traffic: the browser downloads directly from Gitee CDN.
 * This SW runs entirely in the client — no bandwidth cost to the server.
 */

const APK_PATTERN = /\/compress-image_flutter\/releases\/download\//;

self.addEventListener('fetch', (event) => {
  const { request } = event;

  if (request.method !== 'GET') return;
  if (!APK_PATTERN.test(request.url)) return;

  event.respondWith(handleApkRequest(request));
});

async function handleApkRequest(request) {
  // Fetch the actual APK bytes from Gitee (follows redirect automatically).
  // fetch() here is same-origin from the SW's perspective, so the SW can
  // intercept the response and modify its headers before the browser sees it.
  const response = await fetch(request.url, {
    credentials: 'omit',
    mode: 'cors',
  });

  if (!response.ok) {
    return new Response('Download failed', { status: response.status });
  }

  // Gitee CDN returns Content-Type: application/zip for APK files.
  // Override it to the correct MIME type so the browser saves as .apk.
  const correctType = 'application/vnd.android.package-archive';

  // Clone the stream so we can read headers from the original response
  // while passing the body to the new Response. Clone also keeps the original
  // response intact for any other consumers.
  const cloned = response.clone();

  // Build new headers: correct MIME type + preserve Content-Disposition
  // (which carries the correct .apk filename from Gitee).
  const headers = new Headers();
  headers.set('Content-Type', correctType);

  const cd = cloned.headers.get('Content-Disposition');
  if (cd) headers.set('Content-Disposition', cd);

  // Content-Length is omitted — Gitee's redirect chain makes it unreliable
  // and omitting it lets the browser stream the file without expecting
  // a precise total size (a progress bar won't be accurate but the download
  // completes correctly).

  return new Response(cloned.body, {
    status: 200,
    headers,
  });
}
import type { Job, Options } from './types';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '';

export async function createCompressionJob(files: File[], options: Options) {
  const form = new FormData();
  files.forEach((file) => form.append('files', file));
  form.append('target_kb', String(options.targetKb));
  form.append('max_side', String(options.maxSide));
  form.append('output_format', options.outputFormat);
  form.append('min_quality', String(options.minQuality));
  form.append('grayscale', String(options.grayscale));
  form.append('aggressive', String(options.aggressive));

  return fetchJson<Job>(`${API_BASE}/api/jobs`, {
    method: 'POST',
    body: form,
  });
}

export function fetchJob(jobId: string) {
  return fetchJson<Job>(`${API_BASE}/api/jobs/${jobId}`);
}

export function downloadFileUrl(jobId: string, fileId: string) {
  return `${API_BASE}/api/jobs/${jobId}/files/${fileId}/download`;
}

export function downloadZipUrl(jobId: string) {
  return `${API_BASE}/api/jobs/${jobId}/download.zip`;
}

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const payload = await response.json();
      detail = payload.detail ?? detail;
    } catch {
      // Keep the HTTP status text when the response is not JSON.
    }
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}

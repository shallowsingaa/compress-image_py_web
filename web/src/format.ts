import type { JobFile } from './types';

export function statusText(file: JobFile) {
  if (file.status === 'queued') return '等待处理';
  if (file.status === 'processing') return '正在压缩';
  if (file.status === 'error') return file.error ?? '处理失败';
  const sizeText = file.output_width && file.output_height ? `${file.output_width} x ${file.output_height}` : '';
  const targetText = file.success ? '已达目标体积' : '未完全达标';
  return [targetText, sizeText, file.note].filter(Boolean).join(' · ');
}

export function formatBytes(bytes: number) {
  if (!bytes) return '0 KB';
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`;
}

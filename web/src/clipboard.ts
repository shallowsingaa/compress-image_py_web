import { downloadFileUrl } from './api';
import type { JobFile } from './types';

export function isEditableTarget(target: EventTarget | null) {
  if (!(target instanceof HTMLElement)) return false;
  const editable = target.closest('input, textarea, select, [contenteditable="true"]');
  return Boolean(editable);
}

export function extractImageFilesFromClipboardData(data: DataTransfer | null) {
  if (!data) return [];

  const files = Array.from(data.files)
    .filter((file) => file.type.startsWith('image/'))
    .map((file, index) => normalizeClipboardFile(file, index));

  if (files.length) return files;

  return Array.from(data.items)
    .filter((item) => item.kind === 'file' && item.type.startsWith('image/'))
    .map((item, index) => {
      const file = item.getAsFile();
      return file ? normalizeClipboardFile(file, index, item.type) : null;
    })
    .filter((file): file is File => file !== null);
}

export async function extractImageFilesFromClipboardItems(items: ClipboardItem[]) {
  const images: File[] = [];

  for (const item of items) {
    const imageType = item.types.find((type) => type.startsWith('image/'));
    if (!imageType) continue;

    const blob = await item.getType(imageType);
    images.push(
      new File([blob], clipboardFileName(imageType, images.length), {
        type: imageType,
        lastModified: Date.now(),
      }),
    );
  }

  return images;
}

export async function buildCompressedClipboardItems(jobId: string, files: JobFile[]) {
  const items: ClipboardItem[] = [];

  for (const file of files) {
    const { blob, mime } = await fetchCompressedBlob(jobId, file);
    if (!clipboardSupportsMime(mime)) {
      throw new Error(
        `浏览器剪贴板不支持写入 ${mimeToFormatLabel(mime)}，不能在保持输出格式的前提下复制；请使用下载入口，或把输出格式改为 PNG 后重试`,
      );
    }

    const clipboardBlob = new Blob([blob], { type: mime });
    items.push(new ClipboardItem({ [clipboardBlob.type]: clipboardBlob }));
  }

  return items;
}

export function clipboardErrorMessage(err: unknown, fallback: string) {
  if (!(err instanceof Error)) return fallback;
  if (err.name === 'NotAllowedError') return '剪贴板权限被拒绝，请授权后重试，或使用下载入口';
  if (err.name === 'NotFoundError') return '剪贴板里没有可读取的图片';
  return err.message || fallback;
}

function normalizeClipboardFile(file: File, index: number, fallbackType?: string) {
  const type = file.type || fallbackType || 'image/png';
  if (file.name) {
    return new File([file], file.name, { type, lastModified: file.lastModified || Date.now() });
  }
  return new File([file], clipboardFileName(type, index), { type, lastModified: Date.now() });
}

function clipboardFileName(type: string, index: number) {
  const extension = typeToExtension(type);
  const stamp = new Date().toISOString().replace(/[-:T.Z]/g, '').slice(0, 14);
  return `clipboard-${stamp}-${index + 1}.${extension}`;
}

function typeToExtension(type: string) {
  if (type === 'image/jpeg') return 'jpg';
  if (type === 'image/webp') return 'webp';
  if (type === 'image/gif') return 'gif';
  return 'png';
}

async function fetchCompressedBlob(jobId: string, file: JobFile) {
  const response = await fetch(downloadFileUrl(jobId, file.id));
  if (!response.ok) {
    throw new Error(`下载 ${file.output_filename ?? file.filename} 失败`);
  }

  const blob = await response.blob();
  const headerMime = response.headers.get('content-type')?.split(';')[0]?.trim().toLowerCase();
  const mime = normalizeImageMime(headerMime, file.output_format, blob.type);
  return { blob, mime };
}

function normalizeImageMime(headerMime?: string, outputFormat?: string | null, blobType?: string) {
  const candidates = [formatToMime(outputFormat), blobType, headerMime];
  return candidates.find((type) => type?.startsWith('image/')) ?? 'image/png';
}

function formatToMime(format?: string | null) {
  const normalized = format?.toLowerCase();
  if (normalized === 'jpg' || normalized === 'jpeg') return 'image/jpeg';
  if (normalized === 'webp') return 'image/webp';
  if (normalized === 'png') return 'image/png';
  return null;
}

function clipboardSupportsMime(type: string) {
  const ClipboardItemWithSupports = ClipboardItem as typeof ClipboardItem & {
    supports?: (type: string) => boolean;
  };
  return ClipboardItemWithSupports.supports ? ClipboardItemWithSupports.supports(type) : true;
}

function mimeToFormatLabel(type: string) {
  if (type === 'image/jpeg') return 'JPG';
  if (type === 'image/webp') return 'WebP';
  if (type === 'image/png') return 'PNG';
  return type;
}

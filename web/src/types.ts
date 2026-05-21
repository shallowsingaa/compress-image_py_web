export type OutputFormat = 'jpg' | 'png' | 'webp' | 'auto';
export type JobStatus = 'queued' | 'processing' | 'done';
export type FileStatus = 'queued' | 'processing' | 'done' | 'error';

export type JobFile = {
  id: string;
  filename: string;
  status: FileStatus;
  original_size: number;
  original_width: number | null;
  original_height: number | null;
  output_filename: string | null;
  output_size: number | null;
  output_width: number | null;
  output_height: number | null;
  output_format: string | null;
  note: string | null;
  success: boolean | null;
  error: string | null;
  compression_ratio: number | null;
};

export type Job = {
  id: string;
  status: JobStatus;
  total: number;
  completed: number;
  failed: number;
  files: JobFile[];
};

export type Options = {
  targetKb: number;
  maxSide: number;
  outputFormat: OutputFormat;
  minQuality: number;
  grayscale: boolean;
  aggressive: boolean;
};

export type ClipboardTone = 'idle' | 'working' | 'success' | 'warning' | 'error';

export type ClipboardStatus = {
  tone: ClipboardTone;
  message: string;
};

export type DeviceCategory = 'android' | 'harmonyos' | 'ios' | 'desktop';

export type ApkPackage = {
  arch: string;
  url: string;
  description: string;
};

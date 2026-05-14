import { StrictMode, useEffect, useMemo, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import {
  Archive,
  CheckCircle2,
  Download,
  FileArchive,
  ImagePlus,
  Loader2,
  RotateCcw,
  Settings2,
  UploadCloud,
  XCircle,
} from 'lucide-react';
import './styles.css';

type OutputFormat = 'jpg' | 'png' | 'webp' | 'auto';
type JobStatus = 'queued' | 'processing' | 'done';
type FileStatus = 'queued' | 'processing' | 'done' | 'error';

type JobFile = {
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

type Job = {
  id: string;
  status: JobStatus;
  total: number;
  completed: number;
  failed: number;
  files: JobFile[];
};

type Options = {
  targetKb: number;
  maxSide: number;
  outputFormat: OutputFormat;
  minQuality: number;
  grayscale: boolean;
  aggressive: boolean;
};

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '';

function App() {
  const [files, setFiles] = useState<File[]>([]);
  const [job, setJob] = useState<Job | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [options, setOptions] = useState<Options>({
    targetKb: 80,
    maxSide: 1300,
    outputFormat: 'jpg',
    minQuality: 70,
    grayscale: false,
    aggressive: false,
  });
  const inputRef = useRef<HTMLInputElement | null>(null);

  const progress = useMemo(() => {
    if (!job || job.total === 0) return 0;
    return Math.round(((job.completed + job.failed) / job.total) * 100);
  }, [job]);

  const finishedFiles = useMemo(
    () => job?.files.filter((file) => file.status === 'done') ?? [],
    [job],
  );

  useEffect(() => {
    if (!job || job.status === 'done') return;

    const timer = window.setInterval(async () => {
      try {
        const next = await fetchJson<Job>(`${API_BASE}/api/jobs/${job.id}`);
        setJob(next);
      } catch (err) {
        setError(err instanceof Error ? err.message : '查询任务状态失败');
      }
    }, 900);

    return () => window.clearInterval(timer);
  }, [job]);

  function appendFiles(nextFiles: FileList | File[]) {
    const images = Array.from(nextFiles).filter((file) => file.type.startsWith('image/'));
    setFiles((current) => {
      const known = new Set(current.map((file) => `${file.name}-${file.size}-${file.lastModified}`));
      const merged = [...current];
      for (const file of images) {
        const key = `${file.name}-${file.size}-${file.lastModified}`;
        if (!known.has(key)) merged.push(file);
      }
      return merged;
    });
  }

  async function submitJob() {
    if (!files.length) {
      setError('请先选择至少一张图片。');
      return;
    }

    setIsSubmitting(true);
    setError('');
    const form = new FormData();
    files.forEach((file) => form.append('files', file));
    form.append('target_kb', String(options.targetKb));
    form.append('max_side', String(options.maxSide));
    form.append('output_format', options.outputFormat);
    form.append('min_quality', String(options.minQuality));
    form.append('grayscale', String(options.grayscale));
    form.append('aggressive', String(options.aggressive));

    try {
      const created = await fetchJson<Job>(`${API_BASE}/api/jobs`, {
        method: 'POST',
        body: form,
      });
      setJob(created);
    } catch (err) {
      setError(err instanceof Error ? err.message : '创建压缩任务失败');
    } finally {
      setIsSubmitting(false);
    }
  }

  function resetAll() {
    setFiles([]);
    setJob(null);
    setError('');
    if (inputRef.current) inputRef.current.value = '';
  }

  function downloadOne(fileId: string) {
    if (!job) return;
    window.open(`${API_BASE}/api/jobs/${job.id}/files/${fileId}/download`, '_blank');
  }

  function downloadAllIndividually() {
    finishedFiles.forEach((file, index) => {
      window.setTimeout(() => downloadOne(file.id), index * 180);
    });
  }

  function downloadZip() {
    if (!job) return;
    window.open(`${API_BASE}/api/jobs/${job.id}/download.zip`, '_blank');
  }

  return (
    <main className="shell">
      <section className="workspace" aria-label="图片批量压缩工作台">
        <div className="control-pane">
          <div className="masthead">
            <p className="eyebrow">本地批量处理</p>
            <h1>图片批量压缩</h1>
            <p className="intro">适合证件、截图、表格和文字图片，按目标体积生成清晰可下载的结果。</p>
          </div>

          <button
            className={`dropzone ${isDragging ? 'is-dragging' : ''}`}
            type="button"
            onClick={() => inputRef.current?.click()}
            onDragOver={(event) => {
              event.preventDefault();
              setIsDragging(true);
            }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={(event) => {
              event.preventDefault();
              setIsDragging(false);
              appendFiles(event.dataTransfer.files);
            }}
          >
            <UploadCloud aria-hidden="true" />
            <span>拖入图片，或点击选择</span>
            <small>支持多选，非图片文件会自动忽略</small>
          </button>

          <input
            ref={inputRef}
            className="visually-hidden"
            type="file"
            accept="image/*"
            multiple
            onChange={(event) => {
              if (event.target.files) appendFiles(event.target.files);
            }}
          />

          <div className="settings">
            <div className="section-title">
              <Settings2 aria-hidden="true" />
              <span>压缩参数</span>
            </div>

            <label>
              <span>目标体积 KB</span>
              <input
                type="number"
                min={1}
                value={options.targetKb}
                onChange={(event) => setOptions({ ...options, targetKb: Number(event.target.value) })}
              />
            </label>

            <label>
              <span>最长边像素</span>
              <input
                type="number"
                min={1}
                value={options.maxSide}
                onChange={(event) => setOptions({ ...options, maxSide: Number(event.target.value) })}
              />
            </label>

            <label>
              <span>输出格式</span>
              <select
                value={options.outputFormat}
                onChange={(event) =>
                  setOptions({ ...options, outputFormat: event.target.value as OutputFormat })
                }
              >
                <option value="jpg">JPG</option>
                <option value="png">PNG</option>
                <option value="webp">WebP</option>
                <option value="auto">自动选择</option>
              </select>
            </label>

            <label>
              <span>最低质量</span>
              <input
                type="number"
                min={1}
                max={95}
                value={options.minQuality}
                onChange={(event) => setOptions({ ...options, minQuality: Number(event.target.value) })}
              />
            </label>

            <div className="toggle-grid">
              <label className="toggle">
                <input
                  type="checkbox"
                  checked={options.grayscale}
                  onChange={(event) => setOptions({ ...options, grayscale: event.target.checked })}
                />
                <span>灰度压缩</span>
              </label>
              <label className="toggle">
                <input
                  type="checkbox"
                  checked={options.aggressive}
                  onChange={(event) => setOptions({ ...options, aggressive: event.target.checked })}
                />
                <span>激进模式</span>
              </label>
            </div>
          </div>

          {files.length > 0 && (
            <div className="selected">
              <div className="section-title">
                <ImagePlus aria-hidden="true" />
                <span>已选择 {files.length} 张</span>
              </div>
              <div className="selected-list">
                {files.map((file) => (
                  <span key={`${file.name}-${file.size}-${file.lastModified}`}>{file.name}</span>
                ))}
              </div>
            </div>
          )}

          {error && <p className="error-line">{error}</p>}

          <div className="action-row">
            <button className="primary" type="button" onClick={submitJob} disabled={isSubmitting || !files.length}>
              {isSubmitting ? <Loader2 className="spin" aria-hidden="true" /> : <Archive aria-hidden="true" />}
              <span>{isSubmitting ? '提交中' : '开始压缩'}</span>
            </button>
            <button className="secondary" type="button" onClick={resetAll}>
              <RotateCcw aria-hidden="true" />
              <span>重置</span>
            </button>
          </div>
        </div>

        <div className="result-pane">
          <div className="result-head">
            <div>
              <p className="eyebrow">处理队列</p>
              <h2>{job ? `${job.completed + job.failed}/${job.total} 已完成` : '等待上传'}</h2>
            </div>
            <div className="progress-ring" aria-label={`进度 ${progress}%`}>
              {progress}%
            </div>
          </div>

          <div className="progress-track">
            <span style={{ width: `${progress}%` }} />
          </div>

          <div className="download-row">
            <button type="button" onClick={downloadAllIndividually} disabled={!finishedFiles.length}>
              <Download aria-hidden="true" />
              <span>逐个下载全部</span>
            </button>
            <button type="button" onClick={downloadZip} disabled={!finishedFiles.length}>
              <FileArchive aria-hidden="true" />
              <span>下载 ZIP</span>
            </button>
          </div>

          <div className="queue">
            {!job && <EmptyState />}
            {job?.files.map((file) => (
              <ResultItem key={file.id} file={file} onDownload={() => downloadOne(file.id)} />
            ))}
          </div>
        </div>
      </section>
    </main>
  );
}

function ResultItem({ file, onDownload }: { file: JobFile; onDownload: () => void }) {
  const ratio = file.compression_ratio == null ? null : Math.round(file.compression_ratio * 100);

  return (
    <article className="result-item">
      <div className="file-main">
        <div className={`status-dot status-${file.status}`}>
          {file.status === 'done' && <CheckCircle2 aria-hidden="true" />}
          {file.status === 'error' && <XCircle aria-hidden="true" />}
          {(file.status === 'queued' || file.status === 'processing') && (
            <Loader2 className={file.status === 'processing' ? 'spin' : ''} aria-hidden="true" />
          )}
        </div>
        <div className="file-copy">
          <h3>{file.filename}</h3>
          <p>{statusText(file)}</p>
        </div>
      </div>

      <div className="metrics">
        <Metric label="原图" value={formatBytes(file.original_size)} />
        <Metric label="输出" value={file.output_size ? formatBytes(file.output_size) : '-'} />
        <Metric label="压缩率" value={ratio == null ? '-' : `${ratio}%`} />
        <Metric label="格式" value={file.output_format ?? '-'} />
      </div>

      <button className="download-one" type="button" onClick={onDownload} disabled={file.status !== 'done'}>
        <Download aria-hidden="true" />
        <span>下载</span>
      </button>
    </article>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="empty">
      <ImagePlus aria-hidden="true" />
      <p>上传图片后，这里会显示每张图的压缩状态和下载入口。</p>
    </div>
  );
}

function statusText(file: JobFile) {
  if (file.status === 'queued') return '等待处理';
  if (file.status === 'processing') return '正在压缩';
  if (file.status === 'error') return file.error ?? '处理失败';
  const sizeText = file.output_width && file.output_height ? `${file.output_width} x ${file.output_height}` : '';
  const targetText = file.success ? '已达目标体积' : '未完全达标';
  return [targetText, sizeText, file.note].filter(Boolean).join(' · ');
}

function formatBytes(bytes: number) {
  if (!bytes) return '0 KB';
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`;
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

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);

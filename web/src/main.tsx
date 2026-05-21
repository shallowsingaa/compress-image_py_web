import { StrictMode, useEffect, useMemo, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import {
  Archive,
  CheckCircle2,
  Clipboard,
  ClipboardCheck,
  Download,
  FileArchive,
  ImagePlus,
  Loader2,
  RotateCcw,
  Settings2,
  Smartphone,
  UploadCloud,
  X,
  XCircle,
} from 'lucide-react';
import { createCompressionJob, downloadFileUrl, downloadZipUrl, fetchJob } from './api';
import {
  buildCompressedClipboardItems,
  clipboardErrorMessage,
  extractImageFilesFromClipboardData,
  extractImageFilesFromClipboardItems,
  isEditableTarget,
} from './clipboard';
import { detectDevice } from './device';
import { formatBytes, statusText } from './format';
import type { ApkPackage, ClipboardStatus, DeviceCategory, Job, JobFile, Options, OutputFormat } from './types';
import './styles.css';

const APK_PACKAGES: ApkPackage[] = [
  {
    arch: 'arm64-v8a',
    url: 'https://gitee.com/shallowspider/compress-image_flutter/releases/download/v1.0.1/compress-image_arm64-v8a.apk',
    description: '推荐 · 适合近 6 年的主流安卓手机',
  },
  {
    arch: 'armeabi-v7a',
    url: 'https://gitee.com/shallowspider/compress-image_flutter/releases/download/v1.0.1/compress-image_armeabi-v7a.apk',
    description: '适合较早期的 32 位安卓设备',
  },
  {
    arch: 'x86_64',
    url: 'https://gitee.com/shallowspider/compress-image_flutter/releases/download/v1.0.1/compress-image_x86_64.apk',
    description: '适合安卓模拟器或 x86 平板',
  },
];

function App() {
  const [files, setFiles] = useState<File[]>([]);
  const [job, setJob] = useState<Job | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isDesktopClipboard, setIsDesktopClipboard] = useState(false);
  const [isCopyingClipboard, setIsCopyingClipboard] = useState(false);
  const [clipboardJobId, setClipboardJobId] = useState<string | null>(null);
  const [clipboardStatus, setClipboardStatus] = useState<ClipboardStatus>({
    tone: 'idle',
    message: '桌面端可粘贴截图或图片，压缩完成后会尝试复制结果。',
  });
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
  const autoCopyJobRef = useRef<string | null>(null);

  const progress = useMemo(() => {
    if (!job || job.total === 0) return 0;
    return Math.round(((job.completed + job.failed) / job.total) * 100);
  }, [job]);

  const finishedFiles = useMemo(
    () => job?.files.filter((file) => file.status === 'done') ?? [],
    [job],
  );

  const isBusy = isSubmitting || (!!job && job.status !== 'done');

  useEffect(() => {
    setIsDesktopClipboard(detectDevice() === 'desktop');
  }, []);

  useEffect(() => {
    if (!job || job.status === 'done') return;

    const timer = window.setInterval(async () => {
      try {
        const next = await fetchJob(job.id);
        setJob(next);
      } catch (err) {
        setError(err instanceof Error ? err.message : '查询任务状态失败');
      }
    }, 900);

    return () => window.clearInterval(timer);
  }, [job]);

  useEffect(() => {
    if (!isDesktopClipboard) return;

    function handlePaste(event: ClipboardEvent) {
      if (isEditableTarget(event.target)) return;
      const pastedImages = extractImageFilesFromClipboardData(event.clipboardData);
      if (!pastedImages.length) return;

      event.preventDefault();
      void startClipboardJob(pastedImages, 'paste');
    }

    window.addEventListener('paste', handlePaste);
    return () => window.removeEventListener('paste', handlePaste);
  }, [isDesktopClipboard, isBusy, options]);

  useEffect(() => {
    if (!job || job.status !== 'done') return;
    if (job.id !== clipboardJobId || autoCopyJobRef.current === job.id) return;

    autoCopyJobRef.current = job.id;
    if (!finishedFiles.length) {
      setClipboardStatus({
        tone: 'error',
        message: '本批剪贴板图片没有成功结果，请查看失败原因或重新粘贴。',
      });
      return;
    }

    void copyFinishedFilesToClipboard('auto');
  }, [job, clipboardJobId, finishedFiles]);

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

  async function createJob(nextFiles: File[]) {
    setIsSubmitting(true);
    setError('');
    setJob(null);
    try {
      const created = await createCompressionJob(nextFiles, options);
      setJob(created);
      return created;
    } catch (err) {
      setError(err instanceof Error ? err.message : '创建压缩任务失败');
      throw err;
    } finally {
      setIsSubmitting(false);
    }
  }

  async function submitJob() {
    if (!files.length) {
      setError('请先选择至少一张图片。');
      return;
    }

    setClipboardJobId(null);
    autoCopyJobRef.current = null;
    setClipboardStatus({
      tone: 'idle',
      message: '桌面端可粘贴截图或图片，压缩完成后会尝试复制结果。',
    });

    try {
      await createJob(files);
    } catch {
      // createJob has already surfaced the error in the main error line.
    }
  }

  async function startClipboardJob(nextFiles: File[], source: 'paste' | 'manual') {
    if (isBusy) {
      setClipboardStatus({
        tone: 'warning',
        message: '当前批次仍在处理中，完成后再粘贴新的图片。',
      });
      return;
    }

    const images = nextFiles.filter((file) => file.type.startsWith('image/'));
    if (!images.length) {
      setClipboardStatus({
        tone: 'warning',
        message: '剪贴板里没有可处理的图片。',
      });
      return;
    }

    setFiles(images);
    setClipboardJobId(null);
    autoCopyJobRef.current = null;
    setClipboardStatus({
      tone: 'working',
      message: `${source === 'paste' ? '已粘贴' : '已读取'} ${images.length} 张图片，正在提交压缩。`,
    });

    try {
      const created = await createJob(images);
      setClipboardJobId(created.id);
      setClipboardStatus({
        tone: 'working',
        message: `剪贴板批次已提交，等待 ${images.length} 张图片压缩完成。`,
      });
    } catch (err) {
      setClipboardStatus({
        tone: 'error',
        message: err instanceof Error ? err.message : '剪贴板图片提交失败。',
      });
    }
  }

  async function readClipboardImages() {
    if (isBusy) {
      setClipboardStatus({
        tone: 'warning',
        message: '当前批次仍在处理中，完成后再读取剪贴板。',
      });
      return;
    }

    if (!window.isSecureContext || !navigator.clipboard?.read) {
      setClipboardStatus({
        tone: 'error',
        message: '当前浏览器不允许读取剪贴板，请使用 HTTPS、localhost 或直接粘贴图片。',
      });
      return;
    }

    setClipboardStatus({ tone: 'working', message: '正在读取剪贴板图片。' });

    try {
      const clipboardItems = await navigator.clipboard.read();
      const images = await extractImageFilesFromClipboardItems(clipboardItems);
      await startClipboardJob(images, 'manual');
    } catch (err) {
      setClipboardStatus({
        tone: 'error',
        message: clipboardErrorMessage(err, '读取剪贴板失败'),
      });
    }
  }

  async function copyFinishedFilesToClipboard(trigger: 'auto' | 'manual') {
    if (!job || !finishedFiles.length) return;

    if (!window.isSecureContext || !navigator.clipboard?.write || typeof ClipboardItem === 'undefined') {
      setClipboardStatus({
        tone: 'error',
        message: '当前浏览器不允许写入剪贴板，请使用 HTTPS、localhost，或改用下载按钮。',
      });
      return;
    }

    setIsCopyingClipboard(true);
    setClipboardStatus({
      tone: 'working',
      message: trigger === 'auto' ? '压缩完成，正在复制结果到剪贴板。' : '正在复制压缩结果。',
    });

    try {
      const clipboardItems = await buildCompressedClipboardItems(job.id, finishedFiles);
      await navigator.clipboard.write(clipboardItems);
      const multiNote =
        clipboardItems.length > 1 ? '；系统或目标应用可能只接收第一张，下载入口仍保留' : '';
      setClipboardStatus({
        tone: clipboardItems.length > 1 ? 'warning' : 'success',
        message: `已尝试复制 ${clipboardItems.length} 张压缩结果${multiNote}。`,
      });
    } catch (err) {
      setClipboardStatus({
        tone: 'error',
        message: `${trigger === 'auto' ? '自动复制失败' : '复制失败'}：${clipboardErrorMessage(
          err,
          '可点击一键复制结果重试，或使用下载入口',
        )}`,
      });
    } finally {
      setIsCopyingClipboard(false);
    }
  }

  function resetAll() {
    setFiles([]);
    setJob(null);
    setError('');
    setClipboardJobId(null);
    autoCopyJobRef.current = null;
    setClipboardStatus({
      tone: 'idle',
      message: '桌面端可粘贴截图或图片，压缩完成后会尝试复制结果。',
    });
    if (inputRef.current) inputRef.current.value = '';
  }

  function downloadOne(fileId: string) {
    if (!job) return;
    window.open(downloadFileUrl(job.id, fileId), '_blank');
  }

  function downloadAllIndividually() {
    finishedFiles.forEach((file, index) => {
      window.setTimeout(() => downloadOne(file.id), index * 180);
    });
  }

  function downloadZip() {
    if (!job) return;
    window.open(downloadZipUrl(job.id), '_blank');
  }

  return (
    <main className="shell">
      <DownloadAppLauncher />
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
            <small>
              支持多选、拖拽
              {isDesktopClipboard ? '，桌面端也可 Ctrl+V 粘贴截图或图片' : '，非图片文件会自动忽略'}
            </small>
          </button>

          {isDesktopClipboard && (
            <div className="clipboard-entry">
              <button type="button" onClick={readClipboardImages} disabled={isBusy}>
                <Clipboard aria-hidden="true" />
                <span>从剪贴板读取</span>
              </button>
              <span>粘贴会直接按当前参数新建批次</span>
            </div>
          )}

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
            <p className="hint-text"><em>若显示 Failed to Fetch，请尝试刷新网页！！</em></p>
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

          {isDesktopClipboard && (
            <div className={`clipboard-strip clipboard-strip--${clipboardStatus.tone}`}>
              {clipboardStatus.tone === 'success' ? (
                <ClipboardCheck aria-hidden="true" />
              ) : (
                <Clipboard aria-hidden="true" />
              )}
              <span>{clipboardStatus.message}</span>
              <button
                type="button"
                onClick={() => void copyFinishedFilesToClipboard('manual')}
                disabled={!finishedFiles.length || isCopyingClipboard}
              >
                {isCopyingClipboard ? (
                  <Loader2 className="spin" aria-hidden="true" />
                ) : (
                  <ClipboardCheck aria-hidden="true" />
                )}
                <span>{isCopyingClipboard ? '复制中' : '一键复制结果'}</span>
              </button>
            </div>
          )}

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

function DownloadAppLauncher() {
  const [open, setOpen] = useState(false);
  const [device, setDevice] = useState<DeviceCategory>('desktop');
  const panelRef = useRef<HTMLDivElement | null>(null);
  const triggerRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    setDevice(detectDevice());
  }, []);

  useEffect(() => {
    if (!open) return;
    function handleClick(event: MouseEvent) {
      const target = event.target as Node;
      if (panelRef.current?.contains(target) || triggerRef.current?.contains(target)) return;
      setOpen(false);
    }
    function handleKey(event: KeyboardEvent) {
      if (event.key === 'Escape') setOpen(false);
    }
    document.addEventListener('mousedown', handleClick);
    document.addEventListener('keydown', handleKey);
    return () => {
      document.removeEventListener('mousedown', handleClick);
      document.removeEventListener('keydown', handleKey);
    };
  }, [open]);

  return (
    <div className="app-download">
      <button
        ref={triggerRef}
        className="app-download__trigger"
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        aria-haspopup="dialog"
      >
        <Smartphone aria-hidden="true" />
        <span>下载 APP</span>
      </button>

      {open && (
        <div
          ref={panelRef}
          className="app-download__panel"
          role="dialog"
          aria-label="下载图片批量压缩 APP"
        >
          <header className="app-download__head">
            <p className="eyebrow">原生应用</p>
            <h3>{panelHeading(device)}</h3>
            <button
              type="button"
              className="app-download__close"
              onClick={() => setOpen(false)}
              aria-label="关闭"
            >
              <X aria-hidden="true" />
            </button>
          </header>
          <DownloadPanelBody device={device} />
        </div>
      )}
    </div>
  );
}

function panelHeading(device: DeviceCategory) {
  if (device === 'ios') return '哎呀，iOS 还没来';
  if (device === 'harmonyos') return '纯鸿蒙正在打磨';
  if (device === 'android') return '挑一个适合的版本';
  return '装到你的安卓手机上';
}

function DownloadPanelBody({ device }: { device: DeviceCategory }) {
  if (device === 'ios') {
    return (
      <div className="app-download__note">
        <p>你好呀，iPhone 用户~</p>
        <p>
          我们暂时还没有 iOS 版本。网页版的功能其实一模一样，
          先在 Safari 里压缩着用，等我们攒够心意再给你一个原生惊喜。
        </p>
      </div>
    );
  }

  if (device === 'harmonyos') {
    return (
      <div className="app-download__note">
        <p>你好呀，纯鸿蒙伙伴~</p>
        <p>
          纯血 HarmonyOS NEXT 的原生版本还在加紧打磨。
          网页版功能完全够用，先在浏览器里凑合一下，我们尽快奉上。
        </p>
      </div>
    );
  }

  const isAndroid = device === 'android';
  const lead = isAndroid
    ? '已识别到你正在使用 Android 设备，按手机芯片架构挑一个即可。'
    : '想把它装到安卓手机上？根据手机 CPU 架构挑一个安装包。';

  return (
    <>
      <p className="app-download__lead">{lead}</p>
      <ul className="app-download__list">
        {APK_PACKAGES.map((pkg, index) => (
          <li key={pkg.arch}>
            <a
              className={`app-download__item${isAndroid && index === 0 ? ' is-primary' : ''}`}
              href={pkg.url}
              download
              rel="noopener"
            >
              <div className="app-download__item-text">
                <strong>{pkg.arch}</strong>
                <span>{pkg.description}</span>
              </div>
              <Download aria-hidden="true" />
            </a>
          </li>
        ))}
      </ul>
      <p className="app-download__foot">不确定?多数 2019 年以后的安卓手机选 arm64-v8a 就好。</p>
    </>
  );
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);

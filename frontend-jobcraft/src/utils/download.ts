/**
 * T-M6-5：真下载工具——Blob 文件下载与独立 HTML 文档构建（零后端依赖）。
 *
 * - `triggerBlobDownload`：把字符串/ Blob 落成浏览器下载（不依赖服务端文件接口，
 *   磁盘文件在编辑后已过期，前端当前态即权威）；
 * - `downloadElementAsHtml`：把页面中的 A4 渲染节点序列化为独立 .html 文档，
 *   内联页面样式（<style> 文本 + 可取回的外链 CSS），离线双击可直接查看。
 */

/** 收集当前页面样式：内联 style 文本 + 可 fetch 的外链 stylesheet（失败逐个跳过）。 */
async function collectPageCss(): Promise<string> {
  const parts: string[] = [];
  document.querySelectorAll('style').forEach((s) => {
    if (s.textContent) parts.push(s.textContent);
  });
  const links = Array.from(
    document.querySelectorAll<HTMLLinkElement>('link[rel="stylesheet"]'),
  );
  await Promise.all(
    links.map(async (link) => {
      try {
        const res = await fetch(link.href);
        if (res.ok) parts.push(await res.text());
      } catch {
        // 样式取回失败不阻断下载（开发态无外链 / 跨域），文档结构仍完整
      }
    }),
  );
  return parts.join('\n');
}

/** 触发浏览器下载：建 Blob → ObjectURL → 临时 <a download> 点击 → 立即回收。 */
export function triggerBlobDownload(
  content: string | Blob,
  filename: string,
  mimeType: string,
): void {
  const blob =
    typeof content === 'string' ? new Blob([content], { type: mimeType }) : content;
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.style.display = 'none';
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

/**
 * 把指定元素序列化为独立 HTML 文档并下载。
 *
 * @param element 页面中承载内容的根节点（如预览的 A4 页）
 * @param filename 下载文件名（.html）
 * @returns 是否成功触发下载；元素缺失时返回 false 且不触发
 */
export async function downloadElementAsHtml(
  element: HTMLElement | null,
  filename: string,
): Promise<boolean> {
  if (!element) return false;
  const css = await collectPageCss();
  const title = filename.replace(/\.html$/i, '');
  const html = `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>${title}</title>
<style>
${css}
</style>
</head>
<body>
${element.outerHTML}
</body>
</html>`;
  triggerBlobDownload(html, filename, 'text/html;charset=utf-8');
  return true;
}

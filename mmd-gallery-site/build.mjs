import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";

const root = new URL(".", import.meta.url);
const assets = [
  {
    id: "grid",
    title: "Aplaybox MMD models",
    subtitle: "Fixed alpha cutout and outline pass",
    file: "grid.png",
  },
  {
    id: "march7",
    title: "March 7th",
    subtitle: "21,218 verts / 28,039 tris / 30 materials",
    file: "march7.png",
  },
  {
    id: "keqing",
    title: "Keqing",
    subtitle: "25,115 verts / 33,479 tris / 30 materials",
    file: "keqing.png",
  },
  {
    id: "ganyu",
    title: "Ganyu",
    subtitle: "16,589 verts / 21,111 tris / 19 materials",
    file: "ganyu.png",
  },
  {
    id: "raiden",
    title: "Raiden",
    subtitle: "20,614 verts / 25,517 tris / 23 materials",
    file: "raiden.png",
  },
];

const imageData = await Promise.all(
  assets.map(async (asset) => {
    const bytes = await readFile(new URL(`src/assets/${asset.file}`, root));
    return {
      ...asset,
      dataUrl: `data:image/png;base64,${bytes.toString("base64")}`,
    };
  }),
);

const html = `<!doctype html>
<html lang="ko">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
    <title>MMD Preview Gallery</title>
    <style>
      :root {
        color-scheme: dark;
        --bg: #0d0f14;
        --panel: #171a22;
        --text: #f4f7fb;
        --muted: #9da7b8;
        --line: #2b3242;
        --accent: #78c7ff;
      }

      * {
        box-sizing: border-box;
      }

      body {
        margin: 0;
        background: var(--bg);
        color: var(--text);
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      }

      header {
        padding: 22px 16px 14px;
        border-bottom: 1px solid var(--line);
        background: #11141b;
        position: sticky;
        top: 0;
        z-index: 1;
      }

      h1 {
        margin: 0;
        font-size: clamp(22px, 6vw, 36px);
        line-height: 1.08;
        letter-spacing: 0;
      }

      header p {
        margin: 8px 0 0;
        color: var(--muted);
        font-size: 14px;
        line-height: 1.45;
      }

      main {
        width: min(100%, 1480px);
        margin: 0 auto;
        padding: 16px;
      }

      nav {
        display: flex;
        gap: 8px;
        overflow-x: auto;
        padding-bottom: 14px;
      }

      nav a {
        flex: 0 0 auto;
        color: var(--text);
        text-decoration: none;
        border: 1px solid var(--line);
        border-radius: 8px;
        padding: 9px 12px;
        background: #141821;
        font-size: 14px;
      }

      section {
        margin: 0 0 22px;
        border: 1px solid var(--line);
        border-radius: 8px;
        background: var(--panel);
        overflow: hidden;
      }

      .label {
        display: flex;
        justify-content: space-between;
        gap: 12px;
        padding: 12px 14px;
        border-bottom: 1px solid var(--line);
      }

      h2 {
        margin: 0;
        font-size: 17px;
        letter-spacing: 0;
      }

      .label span {
        color: var(--muted);
        font-size: 13px;
        text-align: right;
      }

      img {
        display: block;
        width: 100%;
        height: auto;
        background: #07080b;
      }

      .single img {
        max-height: none;
      }

      footer {
        color: var(--muted);
        padding: 0 16px 24px;
        font-size: 13px;
        text-align: center;
      }

      @media (min-width: 900px) {
        main {
          padding: 22px;
        }

        .singles {
          display: grid;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: 18px;
        }

        .singles section {
          margin: 0;
        }
      }
    </style>
  </head>
  <body>
    <header>
      <h1>MMD Preview Gallery</h1>
      <p>원격 iPhone에서 바로 볼 수 있도록 PNG를 페이지 안에 포함했습니다.</p>
    </header>
    <main>
      <nav>
        ${imageData.map((asset) => `<a href="#${asset.id}">${asset.title}</a>`).join("")}
      </nav>
      <section id="${imageData[0].id}">
        <div class="label">
          <h2>${imageData[0].title}</h2>
          <span>${imageData[0].subtitle}</span>
        </div>
        <img src="${imageData[0].dataUrl}" alt="${imageData[0].title}" />
      </section>
      <div class="singles">
        ${imageData
          .slice(1)
          .map(
            (asset) => `<section id="${asset.id}" class="single">
          <div class="label">
            <h2>${asset.title}</h2>
            <span>${asset.subtitle}</span>
          </div>
          <img src="${asset.dataUrl}" alt="${asset.title}" />
        </section>`,
          )
          .join("")}
      </div>
    </main>
    <footer>Captured from the current OpenGL MMD player with fixed cutout alpha handling.</footer>
  </body>
</html>`;

const worker = `const HTML = ${JSON.stringify(html)};

export default {
  async fetch(request) {
    const url = new URL(request.url);
    if (url.pathname !== "/" && !url.pathname.startsWith("/#")) {
      return new Response("Not found", { status: 404 });
    }
    return new Response(HTML, {
      headers: {
        "content-type": "text/html; charset=utf-8",
        "cache-control": "public, max-age=300",
      },
    });
  },
};
`;

await mkdir(new URL("dist/server", root), { recursive: true });
await mkdir(new URL("dist/.openai", root), { recursive: true });
await writeFile(new URL("dist/gallery.html", root), html);
await writeFile(new URL("dist/server/index.js", root), worker);
await writeFile(new URL("dist/.openai/hosting.json", root), await readFile(new URL(".openai/hosting.json", root)));
console.log("Built dist/gallery.html and dist/server/index.js");

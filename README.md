# Bytivor 的技术小屋

Hexo + Butterfly 中文博客，收录 Bytivor 的图形渲染笔记与作品集。

## 本地运行

安装 Node.js 22 后，在本目录执行：

```bash
npm ci
npm run dev
```

打开 http://127.0.0.1:4000/ 。

## 写文章

```bash
npx hexo new "文章标题"
```

在 `source/_posts/` 编辑 Markdown，图片放在 `source/img/`。

- `_config.yml`：博客标题、作者、网址。
- `_config.butterfly.yml`：菜单、封面、头像、主题选项。
- `source/_posts/`：三篇可删除或改写的示例文章。
- `source/portfolio/index.md`：作品集。
- `source/link/index.md`：常用链接。
- `source/credits/index.md`：主题和示例图片来源。

## 发布至 GitHub Pages

1. 在 Bytivor 账号下创建公开仓库 `bytivor.github.io`，不要初始化 README。
2. 将本项目推送到 `main` 分支。项目中不需要上传 `node_modules` 或 `dist`。
3. 打开仓库 Settings → Pages，在 Build and deployment → Source 中选择 **GitHub Actions**。
4. 在 Actions 页面运行 **Publish blog to GitHub Pages**（或提交一次修改）。
5. 发布成功后访问 https://bytivor.github.io/ 。后续推送 `main` 会自动更新。

## 验证

```bash
npm run build
npm run check
```

生成结果位于 `dist/`。字体、图标和图片灯箱依赖随构建复制到站内，正常阅读不依赖外部 CDN。

## 示例素材

背景及封面引用了参考站公开素材，保留来源与许可说明。它们不是 Bytivor 的原创作品。可在 `source/img/` 替换成自己的图片。示例文章已经明确标注用途，不冒用参考作者的文章。

本项目包含 Sites 私人预览的部署信息；GitHub Pages 独立使用 `.github/workflows/pages.yml`，不依赖 Sites。

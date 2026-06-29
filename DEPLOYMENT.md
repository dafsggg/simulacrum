# Simulacrum 部署指南

## 项目信息

- **项目名**: simulacrum
- **Cloudflare Pages**: https://simulacrum-5w2.pages.dev
- **Cloudflare Account ID**: 368885783c0c7034ce2b21c67bee97df

---

## 自动更新架构

```
GitHub Actions (每天0点)
    │
    ├─ 运行 Python 预测脚本 (30万次模拟)
    ├─ 更新 data.js 等数据文件
    ├─ 提交代码到 GitHub
    └─ 自动部署到 Cloudflare Pages
            │
            └─ 用户访问 https://simulacrum-5w2.pages.dev
```

---

## 部署步骤

### 第一步：创建 GitHub 仓库

1. 访问 https://github.com/new
2. 仓库名：`simulacrum`
3. 设为 Private 或 Public
4. 不要勾选 README、.gitignore 等
5. 点击 "Create repository"

### 第二步：上传代码到 GitHub

在项目根目录执行：

```bash
cd "d:\AI portect\世界杯预测（博主版）"
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/您的用户名/simulacrum.git
git push -u origin main
```

### 第三步：获取 Cloudflare API Token

1. 访问 https://dash.cloudflare.com/profile/api-tokens
2. 点击 "Create Token"
3. 选择 "Edit Cloudflare Workers" 模板
4. 权限设置：
   - Account - Cloudflare Pages - Edit
   - Account - Workers R2 Storage - Edit
5. 点击 "Continue to summary" → "Create Token"
6. **复制保存 token**（只显示一次！）

### 第四步：配置 GitHub Secrets

1. 进入 GitHub 仓库 → Settings → Secrets and variables → Actions
2. 点击 "New repository secret" 添加以下密钥：

| Secret 名称 | 值 | 说明 |
|-------------|-----|------|
| `CLOUDFLARE_API_TOKEN` | 您的 Cloudflare API Token | 从第三步获取 |
| `CLOUDFLARE_ACCOUNT_ID` | `368885783c0c7034ce2b21c67bee97df` | Cloudflare 账户 ID |

### 第五步：启用 GitHub Actions

1. 进入 GitHub 仓库 → Actions
2. 如果看到 "Workflows aren't being run"，点击 "I understand my workflows, go ahead and enable them"
3. 找到 "Auto Update Predictions" workflow

### 第六步：手动触发测试

1. 进入 GitHub 仓库 → Actions → Auto Update Predictions
2. 点击 "Run workflow" → 选择 main 分支 → 点击 "Run workflow"
3. 等待运行完成（约 5-10 分钟）
4. 检查 https://simulacrum-5w2.pages.dev 是否更新

---

## 定时更新说明

### 更新时间

- **每天 UTC 2:00**（北京时间 10:00）
- 可以在 `.github/workflows/auto-update.yml` 中修改 cron 表达式

### 修改更新时间

编辑 `.github/workflows/auto-update.yml`：

```yaml
on:
  schedule:
    - cron: '0 2 * * *'  # UTC 时间
```

Cron 格式：`分 时 日 月 周`

常用时间：
- 北京时间 8:00 → `0 0 * * *`（UTC 0:00）
- 北京时间 10:00 → `0 2 * * *`（UTC 2:00）
- 北京时间 12:00 → `0 4 * * *`（UTC 4:00）

### 修改模拟次数

编辑 `.github/workflows/auto-update.yml`：

```yaml
- name: Run prediction update
  run: |
    cd cup2026predictor
    python -m src.update --sims 300000 --no-parallel
```

将 `--sims 300000` 改为您需要的次数。

---

## 手动触发更新

### 方式一：GitHub Actions 网页

1. 进入 GitHub 仓库 → Actions
2. 点击 "Auto Update Predictions"
3. 点击 "Run workflow" → 选择 main → "Run workflow"

### 方式二：本地命令行

```bash
cd "d:\AI portect\世界杯预测（博主版）\cup2026predictor"
python -m src.update --sims 300000 --no-parallel
wrangler pages deploy web --project-name simulacrum
```

---

## Cloudflare Pages 管理

### 查看部署

访问：https://dash.cloudflare.com/368885783c0c7034ce2b21c67bee97df/pages/view/simulacrum

### 自定义域名

1. 进入 Cloudflare Pages 项目 → Custom domains
2. 点击 "Set up a custom domain"
3. 输入您的域名
4. 按照提示配置 DNS

### 查看部署历史

进入 Cloudflare Pages 项目 → Deployments 标签页

---

## 常见问题

### Q: GitHub Actions 运行失败怎么办？

A: 
1. 进入 Actions → 点击失败的 workflow → 查看错误日志
2. 常见原因：
   - API Token 错误
   - 网络问题（无法拉取赛程数据）
   - 运行时间过长（超过 6 小时）

### Q: 网站访问慢怎么办？

A: Cloudflare 有全球 CDN，国内访问通常比 Vercel 快。如果还是慢，可以：
- 考虑使用国内 CDN（如阿里云 CDN）
- 或者使用国内托管服务

### Q: 如何暂停自动更新？

A: 进入 GitHub 仓库 → Settings → Actions → General → Actions permissions → 选择 "Disable actions"

### Q: 模拟次数影响什么？

A:
- 次数越多，预测越精确
- 但运行时间越长
- 30万次：约 3-5 分钟
- 100万次：约 10-15 分钟
- GitHub Actions 免费额度：每月 2000 分钟（足够每天运行）

---

## 文件结构

```
项目根目录/
├── .github/
│   └── workflows/
│       └── auto-update.yml    # 自动更新工作流
├── cup2026predictor/
│   ├── src/                   # Python 源代码
│   ├── data/                  # 数据文件
│   ├── knowledge/             # 知识库
│   └── web/                   # 网站静态文件
│       ├── _headers           # 缓存配置
│       ├── _redirects         # 重定向规则
│       └── ...
└── DEPLOYMENT.md              # 本文件
```

---

## 技术支持

- Cloudflare Pages 文档：https://developers.cloudflare.com/pages/
- GitHub Actions 文档：https://docs.github.com/en/actions
- Cloudflare 状态页：https://www.cloudflarestatus.com/

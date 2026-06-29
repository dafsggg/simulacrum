# Vercel 部署指南

## 部署方式选择

由于项目是纯静态网站，有两种部署方式：

### 方式一：Vercel Web 界面（推荐，最简单）

#### 步骤 1：注册 Vercel 账号
1. 访问 https://vercel.com
2. 点击 "Sign Up"
3. 选择使用 GitHub / Google / 邮箱 注册

#### 步骤 2：创建项目
1. 登录后点击 "Add New..." → "Project"
2. 如果有 GitHub 仓库，选择 "Import Git Repository"
3. 如果没有，选择 "Import Project Folder"（直接上传文件）

#### 步骤 3：配置项目
- **Framework Preset**: 选择 `Other`
- **Root Directory**: 如果上传整个 cup2026predictor 文件夹，设置为 `web`
- **Build Command**: 留空
- **Output Directory**: 留空

#### 步骤 4：部署
1. 点击 "Deploy"
2. 等待 1-2 分钟
3. 获得 URL：`https://your-project.vercel.app`

---

### 方式二：Vercel CLI（适合技术人员）

#### 步骤 1：安装 Vercel CLI
```powershell
npm install -g vercel
```

#### 步骤 2：登录
```powershell
vercel login
```

#### 步骤 3：部署
```powershell
cd "d:\AI portect\世界杯预测（博主版）\cup2026predictor\web"
vercel
```

#### 步骤 4：生产环境部署
```powershell
vercel --prod
```

---

## 文件结构

部署时需要上传 `web` 目录下的所有文件：

```
web/
├── index.html          # 主页面
├── zh/                 # 中文版
│   ├── index.html
│   └── i18n.js
├── de/                 # 德语版
│   ├── index.html
│   └── i18n.js
├── es/                 # 西班牙语版
│   ├── index.html
│   └── i18n.js
├── pt/                 # 葡萄牙语版
│   ├── index.html
│   └── i18n.js
├── ru/                 # 俄语版
│   ├── index.html
│   └── i18n.js
├── data.js             # 预测数据
├── teams.json          # 球队数据
├── blurbs.js           # 简短播报
├── reports.js          # 报告数据
├── calibration.json   # 校准数据
├── predictor-data.js   # 预测器数据
├── predictor.js        # 预测器逻辑
├── i18n.js            # 国际化
├── html2canvas.min.js # 截图功能
├── favicon.png        # 网站图标
├── apple-touch-icon.png # 苹果图标
├── og-image.png       # 社交分享图
├── robots.txt         # SEO
├── sitemap.xml        # 网站地图
├── llms.txt           # AI 可读
├── _redirects         # 重定向规则
└── vercel.json       # Vercel 配置
```

---

## 自定义域名（可选）

### 添加域名
1. 进入项目 Settings → Domains
2. 输入您的域名（如 `yourdomain.com`）
3. 点击 Add

### 配置 DNS
根据 Vercel 提示，配置 DNS 记录：
- 添加 CNAME 记录指向 `cname.vercel-dns.com`

### HTTPS
Vercel 自动提供免费 SSL 证书

---

## 注意事项

### 1. 部署后需要更新预测数据
由于 Vercel Serverless Functions 有 10 秒执行时间限制，不适合运行 30 万次模拟。

**解决方案**：
- 在本地电脑运行 `python src/update.py` 更新数据
- 重新部署到 Vercel

### 2. 自动更新（可选）
如果需要每天自动更新，可以使用：
- GitHub Actions + Vercel
- 或者设置 Windows 定时任务

### 3. 费用
- ✅ 个人使用完全免费
- 每月 100GB 带宽
- 无限 Serverless Functions 执行时间

---

## 常见问题

### Q: 部署后页面显示空白？
A: 检查 Output Directory 设置是否正确，应该是 `web` 目录

### Q: 页面样式丢失？
A: 确保所有静态资源（CSS、JS、图片）路径正确

### Q: 如何更新网站内容？
A: 修改本地文件后，重新部署即可

---

## 支持

- Vercel 文档：https://vercel.com/docs
- 支持邮箱：support@vercel.com

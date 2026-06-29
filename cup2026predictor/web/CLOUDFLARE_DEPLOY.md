# Cloudflare Pages 部署指南

## 为什么选择 Cloudflare Pages？

- ✅ 完全免费
- ✅ 全球 CDN 加速（国内访问速度快）
- ✅ 自动 HTTPS
- ✅ 无限带宽
- ✅ 支持自定义域名
- ✅ 部署简单

---

## 部署步骤

### 第一步：注册 Cloudflare 账号

1. 访问 https://dash.cloudflare.com/sign-up
2. 输入邮箱和密码
3. 点击 "Create Account"
4. 验证邮箱（Cloudflare 会发一封验证邮件）

### 第二步：创建 Pages 项目

1. 登录 Cloudflare 控制台
2. 在左侧菜单点击 **"Workers & Pages"**
3. 点击 **"Create application"**
4. 选择 **"Pages"** 标签页
5. 点击 **"Upload assets"**（直接上传文件夹）

### 第三步：上传文件

1. 项目名称：输入 `worldcup-predictor`（或您喜欢的名字）
2. 上传方式：
   - 点击 **"select from computer"**
   - 选择文件夹：`d:\AI portect\世界杯预测（博主版）\cup2026predictor\web`
   - 或者直接拖拽 `web` 文件夹到页面上

3. 点击 **"Deploy site"**

### 第四步：等待部署完成

- 部署通常需要 1-2 分钟
- 成功后会显示：
  ```
  🎉 Success! Your site was deployed!
  ```

### 第五步：访问网站

部署成功后，您会获得一个网址：
```
https://worldcup-predictor.pages.dev
```

点击链接即可访问您的网站！

---

## 文件结构

上传的 `web` 文件夹包含以下文件：

```
web/
├── index.html          # 英文首页
├── zh/                 # 中文版
│   ├── index.html
│   └── i18n.js
├── de/                 # 德语版
├── es/                 # 西班牙语版
├── pt/                 # 葡萄牙语版
├── ru/                 # 俄语版
├── data.js             # 预测数据
├── teams.json          # 球队数据
├── _headers            # 缓存配置（已创建）
├── _redirects          # 重定向规则（已创建）
└── ...
```

**注意**：`_headers` 和 `_redirects` 文件已为您创建好，无需额外配置。

---

## 自定义域名（可选）

### 添加自定义域名

1. 进入 Pages 项目设置
2. 点击 **"Custom domains"**
3. 点击 **"Set up a custom domain"**
4. 输入您的域名（如 `worldcup.yourdomain.com`）
5. 点击 **"Continue"**

### 配置 DNS

根据 Cloudflare 提示，在您的域名 DNS 管理处添加 CNAME 记录：
- 名称：`worldcup`（或您的子域名）
- 值：`worldcup-predictor.pages.dev`

### 验证

DNS 生效后（通常几分钟到几小时），Cloudflare 会自动：
- 验证域名
- 签发 SSL 证书
- 启用 HTTPS

---

## 更新网站内容

当需要更新预测数据时：

### 方式一：重新上传（简单）

1. 在本地更新 `data.js` 等文件
2. 进入 Cloudflare Pages 项目
3. 点击 **"Deployments"**
4. 点击 **"Upload new version"**
5. 重新上传 `web` 文件夹

### 方式二：GitHub 自动部署（推荐）

如果您有 GitHub 仓库：

1. 将代码推送到 GitHub
2. 在 Pages 项目设置中连接 GitHub 仓库
3. 设置自动部署分支（如 `main`）
4. 每次推送代码自动部署

---

## 配置说明

### _headers 文件

控制缓存策略：
- 静态资源（JS、CSS、图片）：缓存 1 年
- HTML 页面：不缓存，实时更新
- JSON 数据：缓存 1 小时

### _redirects 文件

配置 URL 重定向：
- 根路径 `/` 重定向到中文页面 `/zh/index.html`
- 各语言版本路径映射
- 短路径重定向

---

## 常见问题

### Q: 国内访问速度怎么样？
A: Cloudflare 在全球有 300+ 数据中心，国内访问速度比 Vercel 快很多。

### Q: 免费版有什么限制？
A: Pages 免费版包括：
- 无限静态站点
- 无限带宽
- 无限构建次数
- 每个项目 1000 次 Functions 调用/天

### Q: 部署失败怎么办？
A: 
1. 检查文件路径是否正确
2. 确保上传的是 `web` 文件夹的内容
3. 查看 Cloudflare 控制台的错误提示

### Q: 如何删除项目？
A: 
1. 进入项目设置
2. 滚动到底部
3. 点击 "Delete project"

---

## 支持资源

- Cloudflare Pages 文档：https://developers.cloudflare.com/pages/
- Cloudflare 社区：https://community.cloudflare.com/
- Cloudflare 状态：https://www.cloudflarestatus.com/

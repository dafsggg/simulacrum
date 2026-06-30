/**
 * Cloudflare Pages Function - 触发 GitHub Actions 更新预测
 * 
 * 这个 API 不需要任何认证，直接返回 GitHub Actions 触发链接
 */

export async function onRequestPost(context) {
  return new Response(JSON.stringify({
    status: 'manual_trigger_required',
    message: 'Please trigger the update on GitHub',
    trigger_url: 'https://github.com/dafsggg/simulacrum/actions/workflows/auto-update.yml',
    instructions: [
      '1. 点击上面的链接打开 GitHub Actions 页面',
      '2. 点击 "Run workflow" 按钮',
      '3. 点击绿色的 "Run workflow" 确认',
      '4. 等待 10-15 分钟完成更新',
      '5. 本页会自动检测更新完成并刷新'
    ]
  }), {
    headers: { 
      'Content-Type': 'application/json',
      'Access-Control-Allow-Origin': '*'
    }
  });
}

export async function onRequest(context) {
  return new Response(JSON.stringify({
    service: 'World Cup Predictor Update API',
    message: 'POST to /api/refresh to get update instructions'
  }), {
    headers: { 
      'Content-Type': 'application/json',
      'Access-Control-Allow-Origin': '*'
    }
  });
}

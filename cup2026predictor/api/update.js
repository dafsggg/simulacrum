/**
 * Cloudflare Pages Function - 手动触发预测更新
 * 
 * 使用方法：
 * POST /api/update
 * Headers: Authorization: Bearer YOUR_SECRET_TOKEN
 */

export async function onRequestPost(context) {
  const { request, env } = context;
  
  // 验证 Secret Token
  const authHeader = request.headers.get('Authorization');
  const expectedToken = env.UPDATE_TOKEN;
  
  if (!expectedToken) {
    return new Response('UPDATE_TOKEN not configured', { status: 500 });
  }
  
  if (!authHeader || authHeader !== `Bearer ${expectedToken}`) {
    return new Response('Unauthorized', { 
      status: 401,
      headers: { 'Content-Type': 'text/plain' }
    });
  }
  
  // 由于 Cloudflare Pages Functions 无法直接运行 Python，
  // 我们返回一个提示，建议通过其他方式触发更新
  
  return new Response(JSON.stringify({
    status: 'manual_trigger_only',
    message: 'Prediction update must be triggered via GitHub Actions or local execution',
    instructions: [
      '1. Push changes to GitHub to trigger auto-update',
      '2. Or run locally: python -m src.update --sims 300000',
      '3. Or use GitHub Actions manual trigger: https://github.com/YOUR_USERNAME/simulacrum/actions/workflows/auto-update.yml'
    ]
  }), {
    headers: { 'Content-Type': 'application/json' }
  });
}

export async function onRequest(context) {
  const { request } = context;
  
  return new Response(JSON.stringify({
    service: 'World Cup Predictor API',
    version: '1.0.0',
    endpoints: {
      POST: '/api/update - Trigger prediction update (requires AUTH_TOKEN)'
    }
  }), {
    headers: { 'Content-Type': 'application/json' }
  });
}

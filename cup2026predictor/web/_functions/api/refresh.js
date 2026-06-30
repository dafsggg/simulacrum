/**
 * Cloudflare Pages Function - 触发 GitHub Actions 更新预测
 * 
 * 使用方法：
 * POST /api/refresh
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
  
  // 触发 GitHub Actions workflow
  const owner = 'dafsggg';
  const repo = 'simulacrum';
  const workflowId = 'auto-update.yml';
  
  try {
    const githubResponse = await fetch(
      `https://api.github.com/repos/${owner}/${repo}/actions/workflows/${workflowId}/runs`,
      {
        method: 'POST',
        headers: {
          'Accept': 'application/vnd.github.v3+json',
          'Authorization': `Bearer ${env.GITHUB_TOKEN}`,
          'X-GitHub-Api-Version': '2022-11-28'
        },
        body: JSON.stringify({
          ref: 'main'
        })
      }
    );
    
    if (!githubResponse.ok) {
      const errorData = await githubResponse.json();
      console.error('GitHub API error:', errorData);
      return new Response(JSON.stringify({
        status: 'error',
        message: 'Failed to trigger GitHub Actions',
        details: errorData.message
      }), {
        status: 500,
        headers: { 'Content-Type': 'application/json' }
      });
    }
    
    const data = await githubResponse.json();
    
    return new Response(JSON.stringify({
      status: 'success',
      message: 'Update started. This may take 10-15 minutes.',
      run_id: data.id,
      check_url: `https://github.com/${owner}/${repo}/actions/runs/${data.id}`
    }), {
      headers: { 'Content-Type': 'application/json' }
    });
    
  } catch (error) {
    console.error('Error triggering update:', error);
    return new Response(JSON.stringify({
      status: 'error',
      message: 'Failed to trigger update',
      error: error.message
    }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' }
    });
  }
}

export async function onRequest(context) {
  const { request } = context;
  
  return new Response(JSON.stringify({
    service: 'World Cup Predictor Update API',
    version: '1.0.0',
    endpoints: {
      POST: '/api/refresh - Trigger prediction update (requires AUTH_TOKEN)'
    }
  }), {
    headers: { 'Content-Type': 'application/json' }
  });
}

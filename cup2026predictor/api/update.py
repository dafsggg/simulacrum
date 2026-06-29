"""
Vercel Serverless Function - 预测更新接口
当用户点击"更新预测"按钮时调用此函数
"""
import json
import os
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / 'src'))

def handler(req, res):
    """处理预测更新请求"""
    res.setHeader('Content-Type', 'application/json; charset=utf-8')
    res.setHeader('Access-Control-Allow-Origin', '*')
    
    try:
        # 运行预测更新
        from update import run as run_update
        
        result = run_update(
            sims=300_000,
            seed=None,
            do_fetch=True,
            workers=1,  # Serverless 环境限制单进程
            refresh_all=False,
        )
        
        res.status(200).json({
            'ok': True,
            'message': '预测更新成功',
            'data': result
        })
        
    except Exception as e:
        res.status(500).json({
            'ok': False,
            'error': str(e)
        })

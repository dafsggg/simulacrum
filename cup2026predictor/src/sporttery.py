import json
import time
import urllib.request
from pathlib import Path

from ._paths import ROOT

CACHE = ROOT / 'data' / 'sporttery_odds.json'
API_URL = 'https://webapi.sporttery.cn/gateway/uniform/football/getMatchCalculatorV1.qry'
CACHE_AGE = 30 * 60

CN_TO_CODE = {
    '比利时': 'BEL', '埃及': 'EGY', '沙特阿拉伯': 'KSA', '乌拉圭': 'URU',
    '伊朗': 'IRN', '新西兰': 'NZL', '法国': 'FRA', '塞内加尔': 'SEN',
    '阿根廷': 'ARG', '阿尔及利亚': 'ALG', '奥地利': 'AUT', '约旦': 'JOR',
    '葡萄牙': 'POR', '刚果(金)': 'COD', '英格兰': 'ENG', '克罗地亚': 'CRO',
    '加纳': 'GHA', '巴拿马': 'PAN', '乌兹别克斯坦': 'UZB', '哥伦比亚': 'COL',
    '墨西哥': 'MEX', '南非': 'RSA', '韩国': 'KOR', '捷克': 'CZE',
    '加拿大': 'CAN', '波黑': 'BIH', '卡塔尔': 'QAT', '瑞士': 'SUI',
    '巴西': 'BRA', '摩洛哥': 'MAR', '海地': 'HAI', '苏格兰': 'SCO',
    '美国': 'USA', '巴拉圭': 'PAR', '澳大利亚': 'AUS', '土耳其': 'TUR',
    '德国': 'GER', '库拉索': 'CUW', '西班牙': 'ESP', '洪都拉斯': 'HON',
    '冰岛': 'ISL', '格鲁吉亚': 'GEO', '丹麦': 'DEN',
    '瑞典': 'SWE', '芬兰': 'FIN', '塞尔维亚': 'SRB', '斯洛文尼亚': 'SVN',
    '匈牙利': 'HUN', '波兰': 'POL', '荷兰': 'NED',
    '希腊': 'GRE', '罗马尼亚': 'ROU', '威尔士': 'WAL',
    '斯洛伐克': 'SVK', '北爱尔兰': 'NIR', '以色列': 'ISR',
    '哥斯达黎加': 'CRC', '危地马拉': 'GUA',
    '厄瓜多尔': 'ECU', '委内瑞拉': 'VEN', '玻利维亚': 'BOL', '智利': 'CHI',
    '突尼斯': 'TUN', '尼日利亚': 'NGA', '喀麦隆': 'CMR', '科特迪瓦': 'CIV',
    '马里': 'MLI', '日本': 'JPN', '中国': 'CHN',
    '阿联酋': 'UAE', '伊拉克': 'IRQ', '叙利亚': 'SYR',
    '阿曼': 'OMA', '巴林': 'BRN',
    '塔吉克斯坦': 'TJK',
    '泰国': 'THA', '越南': 'VNM', '马来西亚': 'MAS', '新加坡': 'SIN',
    '印尼': 'IDN', '菲律宾': 'PHI', '缅甸': 'MYA',
    '刚果(布)': 'COG',
}


def _fetch():
    url = API_URL + '?poolCode=had'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Linux; Android 11) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Mobile Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Referer': 'https://m.sporttery.cn/',
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as resp:
        raw = resp.read()
    if raw.startswith(b'\xef\xbb\xbf'):
        raw = raw[3:]
    data = json.loads(raw.decode('utf-8-sig'))
    if not data.get('success') or 'value' not in data:
        return {}
    h2h = {}
    for day in data['value'].get('matchInfoList', []):
        for m in day.get('subMatchList', []):
            had = m.get('had', {})
            if not had or had.get('h') == '0':
                continue
            home_cn = m.get('homeTeamAllName', '')
            away_cn = m.get('awayTeamAllName', '')
            home_code = CN_TO_CODE.get(home_cn)
            away_code = CN_TO_CODE.get(away_cn)
            if not home_code or not away_code:
                continue
            h_odd = float(had.get('h', 0))
            d_odd = float(had.get('d', 0))
            a_odd = float(had.get('a', 0))
            inv_H = 1.0 / h_odd if h_odd > 1 else 0
            inv_D = 1.0 / d_odd if d_odd > 1 else 0
            inv_A = 1.0 / a_odd if a_odd > 1 else 0
            total_inv = inv_H + inv_D + inv_A
            if total_inv > 0:
                p_home = inv_H / total_inv
                p_draw = inv_D / total_inv
                p_away = inv_A / total_inv
            else:
                p_home = p_draw = p_away = 0
            key = home_code + '|' + away_code
            h2h[key] = {
                'p_home': round(p_home, 4),
                'p_draw': round(p_draw, 4),
                'p_away': round(p_away, 4),
                'odds_h': h_odd,
                'odds_d': d_odd,
                'odds_a': a_odd,
                'source': 'sporttery',
            }
    return {'h2h': h2h, 'ts': time.time(), 'last_update': data.get('value', {}).get('lastUpdateTime', '')}


def load():
    if CACHE.exists():
        cached = json.loads(CACHE.read_text(encoding='utf-8'))
        if time.time() - cached.get('ts', 0) < CACHE_AGE:
            return cached
    return None


def sync(quiet=False):
    try:
        result = _fetch()
        if result and result.get('h2h'):
            CACHE.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding='utf-8')
            if not quiet:
                print('  [sporttery] 已更新 ' + str(len(result['h2h'])) + ' 场赔率')
            return result
    except Exception as exc:
        if not quiet:
            print('  [sporttery] 抓取失败（' + str(exc) + '），沿用缓存')
    return load()


if __name__ == '__main__':
    sync()

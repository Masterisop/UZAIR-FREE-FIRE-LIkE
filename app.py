# === like_api.py ===
# MINISTER LIKE API v3.1 - FULLY FIXED FOR PYTHON 3.13
# POWERED BY : @minister_69

from flask import Flask, request, jsonify
import asyncio
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from google.protobuf.json_format import MessageToJson
import binascii
import aiohttp
import requests
import json
import like_pb2
import like_count_pb2
import uid_generator_pb2
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import random
import os
import urllib.parse
import jwt
import ssl
import threading
import traceback

app = Flask(__name__)

# ======================= CONFIGURATION =======================
KEY_LIMIT = 90
tracker = defaultdict(lambda: [0, time.time()])
liked_cache = defaultdict(set)
TOKEN_CACHE = {}
LIKED_CACHE_FILE = "liked_cache.json"
ACCOUNT_FILES = ["account_ind.txt", "account_br.txt", "account_bd.txt", "account_pk.txt"]

# SSL Context
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# ======================= TIME UTILITIES (Python 3.13 Compatible) =======================
def utc_now():
    """Get current UTC datetime (Python 3.13 compatible)"""
    return datetime.now(timezone.utc)

def from_timestamp(ts):
    """Convert timestamp to UTC datetime (Python 3.13 compatible)"""
    return datetime.fromtimestamp(ts, tz=timezone.utc)

# ======================= CACHE PERSISTENCE =======================
def save_liked_cache():
    """Save liked cache to file"""
    try:
        data = {k: list(v) for k, v in liked_cache.items()}
        with open(LIKED_CACHE_FILE, 'w') as f:
            json.dump(data, f)
        print(f"💾 Liked cache saved: {len(data)} entries")
    except Exception as e:
        print(f"⚠️ Failed to save cache: {e}")

def load_liked_cache():
    """Load liked cache from file"""
    global liked_cache
    if os.path.exists(LIKED_CACHE_FILE):
        try:
            with open(LIKED_CACHE_FILE, 'r') as f:
                data = json.load(f)
                for k, v in data.items():
                    liked_cache[k] = set(v)
            print(f"📂 Liked cache loaded: {len(data)} entries")
        except Exception as e:
            print(f"⚠️ Failed to load cache: {e}")

# ======================= ACCOUNT LOADING =======================
def load_accounts_from_file(filename):
    """Load accounts from a specific file"""
    accounts = []
    if not os.path.exists(filename):
        return accounts
    
    try:
        with open(filename, "r", encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if ':' in line:
                    parts = line.split(':', 1)
                    uid = parts[0].strip()
                    password = parts[1].strip()
                    if uid and password and uid.isdigit():
                        accounts.append({"uid": uid, "password": password})
    except Exception as e:
        print(f"❌ Error loading {filename}: {e}")
    
    return accounts

def load_accounts(server_name):
    """Load accounts with fallback to all files"""
    server_files = {
        "IND": "account_ind.txt",
        "BR": "account_br.txt",
        "US": "account_br.txt",
        "SAC": "account_br.txt",
        "NA": "account_br.txt",
        "PK": "account_pk.txt",
        "BD": "account_bd.txt",
        "RU": "account_bd.txt"
    }
    
    filename = server_files.get(server_name, "account_ind.txt")
    print(f"🔍 Looking for: {filename} for server {server_name}")
    
    accounts = load_accounts_from_file(filename)
    if accounts:
        print(f"✅ Loaded {len(accounts)} accounts from {filename}")
        return accounts
    
    print(f"⚠️ {filename} not found or empty, trying fallbacks...")
    all_accounts = []
    for f in ACCOUNT_FILES:
        if os.path.exists(f):
            accs = load_accounts_from_file(f)
            if accs:
                all_accounts.extend(accs)
                print(f"✅ Loaded {len(accs)} from fallback {f}")
    
    if all_accounts:
        print(f"✅ Total {len(all_accounts)} accounts loaded from fallbacks")
        return all_accounts
    
    print(f"❌ No accounts found!")
    return []

# ======================= TOKEN GENERATION =======================
async def generate_jwt_token(uid, password):
    """Generate JWT token with full response parsing"""
    try:
        encoded_password = urllib.parse.quote(password)
        url = f"http://jwt.thug4ff.xyz/token?uid={uid}&password={encoded_password}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=30) as response:
                if response.status == 200:
                    data = await response.json()
                    if isinstance(data, dict) and not data.get('error', True):
                        token = data.get('token') or data.get('jwt_token') or data.get('token_access')
                        if token:
                            return {
                                'token': token,
                                'api': data.get('api'),
                                'server': data.get('server'),
                                'account_id': data.get('account_id'),
                                'status_code': data.get('status_code')
                            }
                return None
    except Exception as e:
        print(f"❌ Token error for {uid}: {e}")
        return None

async def get_valid_token(uid, password):
    """Get valid token with enhanced caching"""
    if uid in TOKEN_CACHE:
        cached = TOKEN_CACHE[uid]
        if cached.get('expires_at'):
            remaining = (cached['expires_at'] - utc_now()).total_seconds()
            if remaining > 1800:  # 30 minutes
                return cached['token']
        else:
            return cached['token']
    
    result = await generate_jwt_token(uid, password)
    if not result:
        return None
    
    token = result['token']
    
    try:
        payload = jwt.decode(token, options={"verify_signature": False})
        exp = payload.get('exp', 0)
        if exp and exp > 0:
            expires_at = from_timestamp(exp)
        else:
            expires_at = utc_now() + timedelta(hours=24)
    except Exception as e:
        print(f"⚠️ JWT decode error: {e}")
        expires_at = utc_now() + timedelta(hours=24)
    
    TOKEN_CACHE[uid] = {
        'token': token,
        'expires_at': expires_at,
        'api_endpoint': result.get('api'),
        'server': result.get('server'),
        'account_id': result.get('account_id')
    }
    
    return token

# ======================= ENCRYPTION =======================
def encrypt_message(plaintext):
    key = b'Yg&tc%DEuh6%Zc^8'
    iv = b'6oyZDr22E3ychjM%'
    cipher = AES.new(key, AES.MODE_CBC, iv)
    padded_message = pad(plaintext, AES.block_size)
    return binascii.hexlify(cipher.encrypt(padded_message)).decode('utf-8')

def enc(uid):
    message = uid_generator_pb2.uid_generator()
    message.krishna_ = int(uid)
    message.teamXdarks = 1
    return encrypt_message(message.SerializeToString())

# ======================= PROTOBUF =======================
def create_protobuf_message(user_id, region):
    message = like_pb2.like()
    message.uid = int(user_id)
    
    region_map = {
        "IND": "IND", "BD": "BD", "BR": "BR", "PK": "PK",
        "US": "US", "SAC": "SAC", "NA": "NA", "RU": "RU"
    }
    message.region = region_map.get(region, region)
    return message.SerializeToString()

def decode_protobuf(binary):
    try:
        items = like_count_pb2.Info()
        items.ParseFromString(binary)
        return items
    except Exception as e:
        print(f"⚠️ Protobuf decode error: {e}")
        return None

# ======================= API ENDPOINTS =======================
def get_api_endpoints(server_name):
    """Get working endpoints with dynamic fallback from token cache"""
    for uid, cache in TOKEN_CACHE.items():
        if cache.get('server') == server_name and cache.get('api_endpoint'):
            endpoint = cache['api_endpoint']
            return {"primary": endpoint, "fallbacks": [endpoint]}
    
    endpoints = {
        "primary": {
            "IND": "https://client.ind.freefiremobile.com",
            "BR": "https://client.us.freefiremobile.com",
            "US": "https://client.us.freefiremobile.com",
            "SAC": "https://client.us.freefiremobile.com",
            "NA": "https://client.us.freefiremobile.com",
            "PK": "https://client.us.freefiremobile.com",
            "BD": "https://clientbp.ggpolarbear.com",
            "RU": "https://clientbp.ggpolarbear.com"
        },
        "fallbacks": {
            "PK": ["https://clientbp.ggpolarbear.com", "https://client.freefiremobile.com"],
            "BD": ["https://client.us.freefiremobile.com"],
            "IND": ["https://clientbp.ggpolarbear.com"],
            "BR": ["https://clientbp.ggpolarbear.com"]
        }
    }
    
    base = endpoints["primary"].get(server_name, "https://clientbp.ggpolarbear.com")
    fallbacks = endpoints["fallbacks"].get(server_name, ["https://clientbp.ggpolarbear.com"])
    
    return {"primary": base, "fallbacks": fallbacks}

def safe_get_player_info(data, field, default=0):
    """Safely extract player info with fallback"""
    try:
        if isinstance(data, dict):
            account_info = data.get('AccountInfo', {})
            if isinstance(account_info, dict):
                return account_info.get(field, default)
            elif hasattr(account_info, field):
                return getattr(account_info, field, default)
        return default
    except Exception:
        return default

def get_player_info(encrypted_uid, server_name, token):
    """Get player info with fallback"""
    endpoints = get_api_endpoints(server_name)
    
    urls_to_try = []
    urls_to_try.append(f"{endpoints['primary']}/GetPlayerPersonalShow")
    for fallback in endpoints['fallbacks']:
        urls_to_try.append(f"{fallback}/GetPlayerPersonalShow")
    urls_to_try = list(dict.fromkeys(urls_to_try))
    
    headers = {
        'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 9; ASUS_Z01QD Build/PI)',
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/x-www-form-urlencoded',
        'X-GA': 'v1 1',
        'ReleaseVersion': 'OB54'
    }
    
    edata = bytes.fromhex(encrypted_uid)
    
    for url in urls_to_try:
        try:
            print(f"🔄 Trying: {url}")
            response = requests.post(url, data=edata, headers=headers, verify=False, timeout=15)
            if response and response.status_code == 200:
                print(f"✅ Success: {url}")
                return decode_protobuf(response.content)
        except Exception as e:
            print(f"⚠️ Error: {e}")
            continue
    
    return None

async def send_like(encrypted_uid, token, server_name):
    """Send like with fallback"""
    endpoints = get_api_endpoints(server_name)
    
    urls_to_try = []
    urls_to_try.append(f"{endpoints['primary']}/LikeProfile")
    for fallback in endpoints['fallbacks']:
        urls_to_try.append(f"{fallback}/LikeProfile")
    urls_to_try = list(dict.fromkeys(urls_to_try))
    
    headers = {
        'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 9; ASUS_Z01QD Build/PI)',
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/x-www-form-urlencoded',
        'X-GA': 'v1 1',
        'ReleaseVersion': 'OB54'
    }
    
    edata = bytes.fromhex(encrypted_uid)
    
    for url in urls_to_try:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=edata, headers=headers, timeout=aiohttp.ClientTimeout(total=10), ssl=False) as response:
                    if response.status == 200:
                        return response.status, url
        except:
            continue
    
    return 500, None

# ======================= MAIN LOGIC =======================
async def process_account(target_uid, encrypted_uid, account, semaphore, server_name):
    async with semaphore:
        try:
            token = await get_valid_token(account['uid'], account['password'])
            if not token:
                return 500, account['uid']
            
            status, _ = await send_like(encrypted_uid, token, server_name)
            
            if status == 200:
                liked_cache[target_uid].add(account['uid'])
                return status, account['uid']
            
            return status, account['uid']
        except Exception as e:
            print(f"⚠️ Process error: {e}")
            return 500, account['uid']

async def send_all_likes(target_uid, server_name):
    protobuf_message = create_protobuf_message(target_uid, server_name)
    encrypted_uid = encrypt_message(protobuf_message)
    
    accounts = load_accounts(server_name)
    if not accounts:
        return {'success': 0, 'failed': 0, 'total': 0, 'already_liked': 0, 'fresh_used': 0}
    
    already_liked = liked_cache.get(target_uid, set())
    fresh_accounts = [acc for acc in accounts if acc['uid'] not in already_liked]
    
    print(f"📊 Total: {len(accounts)} | Fresh: {len(fresh_accounts)} | Already: {len(already_liked)}")
    
    if not fresh_accounts:
        return {
            'success': 0, 
            'failed': 0, 
            'total': len(accounts),
            'already_liked': len(already_liked),
            'fresh_used': 0
        }
    
    random.shuffle(fresh_accounts)
    semaphore = asyncio.Semaphore(20)
    tasks = []
    
    max_accounts = min(len(fresh_accounts), 1000)
    for acc in fresh_accounts[:max_accounts]:
        tasks.append(process_account(target_uid, encrypted_uid, acc, semaphore, server_name))
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    successful = 0
    failed = 0
    for r in results:
        if isinstance(r, tuple):
            if r[0] == 200:
                successful += 1
            else:
                failed += 1
        else:
            failed += 1
    
    if successful > 0:
        threading.Thread(target=save_liked_cache, daemon=True).start()
    
    return {
        'success': successful,
        'failed': failed,
        'total': len(accounts),
        'already_liked': len(already_liked),
        'fresh_used': len(fresh_accounts[:max_accounts])
    }

# ======================= FLASK ROUTES =======================
@app.route('/like', methods=['GET'])
def handle_requests():
    uid = request.args.get("uid")
    server_name = request.args.get("server_name", "").upper()
    key = request.args.get("key")
    client_ip = request.remote_addr

    if key != "JMLB":
        return jsonify({"error": "Invalid API key 🔑"}), 403

    if not uid or not server_name:
        return jsonify({"error": "UID and server_name required"}), 400
    
    try:
        uid_int = int(uid)
        if uid_int <= 0:
            return jsonify({"error": "Invalid UID"}), 400
    except ValueError:
        return jsonify({"error": "UID must be number"}), 400

    valid_servers = ["IND", "BR", "US", "SAC", "NA", "BD", "RU", "PK"]
    if server_name not in valid_servers:
        return jsonify({"error": f"Invalid server. Use: {valid_servers}"}), 400

    today_midnight = get_today_midnight_timestamp()
    count, last_reset = tracker[client_ip]
    if last_reset < today_midnight:
        tracker[client_ip] = [0, time.time()]
        count = 0

    if count >= KEY_LIMIT:
        return jsonify({"error": "Daily limit reached", "remains": f"(0/{KEY_LIMIT})"}), 429

    accounts = load_accounts(server_name)
    if not accounts:
        return jsonify({"error": f"No accounts for {server_name}"}), 500
    
    check_token = None
    for account in accounts[:5]:
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            check_token = loop.run_until_complete(get_valid_token(account['uid'], account['password']))
            loop.close()
            if check_token:
                break
        except Exception as e:
            print(f"⚠️ Token check error: {e}")
            continue
    
    if not check_token:
        return jsonify({"error": "Token generation failed"}), 500
    
    encrypted_uid = enc(uid)
    
    before = get_player_info(encrypted_uid, server_name, check_token)
    if before is None:
        return jsonify({"error": "Could not get player info", "status": 0}), 200

    try:
        before_data = json.loads(MessageToJson(before))
        # ✅ SAFE EXTRACTION — FIXES KeyError
        before_like = safe_get_player_info(before_data, 'Likes', 0)
        print(f"📊 Before likes: {before_like}")
    except Exception as e:
        print(f"⚠️ Before parse error: {e}")
        return jsonify({"error": "Data parsing failed"}), 200

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(send_all_likes(uid, server_name))
        loop.close()
    except Exception as e:
        print(f"❌ Send likes error: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e), "status": 0}), 500

    after = get_player_info(encrypted_uid, server_name, check_token)
    if after is None:
        return jsonify({"error": "Could not verify likes after"}), 200

    try:
        after_data = json.loads(MessageToJson(after))
        # ✅ SAFE EXTRACTION — FIXES KeyError
        after_like = safe_get_player_info(after_data, 'Likes', 0)
        player_name = safe_get_player_info(after_data, 'PlayerNickname', 'Unknown')
        print(f"📊 After likes: {after_like}")
        
        like_given = after_like - before_like
        status = 1 if like_given > 0 else 2
        
        if like_given > 0:
            tracker[client_ip][0] += 1
            count += 1
        
        remains = KEY_LIMIT - count

        return jsonify({
            "LikesGivenByAPI": like_given,
            "LikesafterCommand": after_like,
            "LikesbeforeCommand": before_like,
            "PlayerNickname": player_name,
            "UID": uid,
            "status": status,
            "remains": f"({remains}/{KEY_LIMIT})",
            "server": server_name,
            "accounts_used": result.get('fresh_used', 0),
            "successful_likes": result.get('success', 0),
            "failed_likes": result.get('failed', 0),
            "total_accounts": result.get('total', 0)
        })
    except Exception as e:
        print(f"❌ Final parse error: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e), "status": 0}), 500

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        "status": "working",
        "servers": ["IND", "BR", "US", "SAC", "NA", "BD", "RU", "PK"],
        "version": "3.1",
        "credit": "@minister_69",
        "cache_size": len(TOKEN_CACHE),
        "liked_cache_size": len(liked_cache)
    })

@app.route('/reset-cache', methods=['GET'])
def reset_cache():
    key = request.args.get("key")
    if key != "JMLB":
        return jsonify({"error": "Invalid key"}), 403
    
    global liked_cache, TOKEN_CACHE, tracker
    liked_cache.clear()
    TOKEN_CACHE.clear()
    tracker.clear()
    
    if os.path.exists(LIKED_CACHE_FILE):
        os.remove(LIKED_CACHE_FILE)
    
    return jsonify({"message": "All caches cleared", "credit": "@minister_69"})

@app.route('/stats', methods=['GET'])
def get_stats():
    key = request.args.get("key")
    if key != "JMLB":
        return jsonify({"error": "Invalid key"}), 403
    
    total_accounts = {}
    for f in ACCOUNT_FILES:
        if os.path.exists(f):
            count = sum(1 for line in open(f, 'r', encoding='utf-8') 
                       if line.strip() and not line.startswith('#') and ':' in line)
            total_accounts[f] = count
    
    return jsonify({
        "token_cache": len(TOKEN_CACHE),
        "liked_cache_entries": len(liked_cache),
        "account_files": total_accounts,
        "daily_ips": len(tracker)
    })

def get_today_midnight_timestamp():
    now = datetime.now()
    midnight = datetime(now.year, now.month, now.day)
    return midnight.timestamp()

# ======================= CHECK ALL ACCOUNT FILES =======================
def check_account_files():
    """Check and display all account files"""
    files = {
        "account_ind.txt": "IND Server",
        "account_br.txt": "BR/US/SAC/NA Servers",
        "account_pk.txt": "PK Server",
        "account_bd.txt": "BD/RU Server"
    }
    
    print("\n📁 ACCOUNT FILES STATUS:")
    print("=" * 50)
    
    total_accounts = 0
    for filename, description in files.items():
        if os.path.exists(filename):
            count = 0
            try:
                with open(filename, "r", encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and ':' in line:
                            count += 1
                total_accounts += count
            except:
                pass
            print(f"✅ {filename:20} - {description:25} ({count} accounts)")
        else:
            print(f"❌ {filename:20} - {description:25} (NOT FOUND)")
    
    print("=" * 50)
    print(f"📊 Total accounts across all files: {total_accounts}")
    print("=" * 50)

# ======================= MAIN =======================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    
    print("=" * 60)
    print("🚀 MINISTER LIKE API v3.1 - FULLY FIXED")
    print("=" * 60)
    
    load_liked_cache()
    check_account_files()
    
    print("\n🌍 SMART ENDPOINT SYSTEM:")
    print("   ✅ Dynamic endpoint from token response")
    print("   ✅ PK server uses US endpoints (reliable)")
    print("   ✅ Automatic fallback to global servers")
    print("   ✅ SSL verification bypassed")
    print("\n🔧 Features:")
    print("   ✅ Smart endpoint selection")
    print("   ✅ Multiple fallback URLs")
    print("   ✅ Account caching with persistence")
    print("   ✅ Daily limit: 90/IP")
    print("   ✅ Automatic retry on failure")
    print("   ✅ Cross-server account fallback")
    print("   ✅ Fixed token parsing (token_access)")
    print("   ✅ Fixed JWT expiry handling")
    print("   ✅ Proper event loop management")
    print("   ✅ Python 3.13 compatible (no deprecation warnings)")
    print("   ✅ Safe field extraction (no KeyError)")
    print("=" * 60)
    print(f"🏃 Starting server on http://0.0.0.0:{port}")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

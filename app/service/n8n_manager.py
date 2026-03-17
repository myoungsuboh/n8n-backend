import os
import json
import requests
from dotenv import load_dotenv
from typing import List

load_dotenv()

N8N_BASE_URL = os.getenv("N8N_BASE_URL")
N8N_API_KEY = os.getenv("N8N_API_KEY")

HEADERS = {"X-N8N-API-KEY": N8N_API_KEY}

# 경로 설정
RESOURCES_PATH = os.path.join(os.getcwd(), "resources")

BASE_DIRS = {
    "SKELETON": os.path.join(RESOURCES_PATH, "skeletons"),
    "COMPONENT": os.path.join(RESOURCES_PATH, "components")
}

def get_node_info(node_type_name: str):
    """
    특정 노드의 상세 파라미터와 설정법(Schema)을 가져옵니다.
    예: 'n8n-nodes-base.httpRequest'
    """
    # n8n은 모든 노드 정의를 /node-types 엔드포인트에서 제공합니다.
    endpoint = f"{N8N_BASE_URL}/node-types"
    
    try:
        response = requests.get(endpoint, headers=HEADERS)
        response.raise_for_status()
        nodes = response.json()
        
        # 요청한 노드 타입과 일치하는 정보 찾기
        node_info = next((node for node in nodes if node['name'] == node_type_name), None)
        
        if node_info:
            print(f"✅ {node_type_name} 노드 정보를 찾았습니다.")
            return node_info
        else:
            return {"error": f"Node type '{node_type_name}' not found."}
            
    except Exception as e:
        return {"error": str(e)}

def get_execution_logs(execution_id: str):
    """
    특정 실행 ID의 상세 로그(성공 여부, 에러 메시지 등)를 가져옵니다.
    """
    endpoint = f"{N8N_BASE_URL}/executions/{execution_id}"
    
    try:
        response = requests.get(endpoint, headers=HEADERS)
        response.raise_for_status()
        execution_data = response.json()
        
        # 에이전트가 이해하기 쉽게 필요한 정보만 추출
        log_summary = {
            "id": execution_data.get("id"),
            "status": execution_data.get("status"),
            "error": execution_data.get("data", {}).get("resultData", {}).get("error"),
            "finished": execution_data.get("finished"),
            "mode": execution_data.get("mode")
        }
        
        print(f"✅ 실행 ID {execution_id}의 로그를 가져왔습니다. 상태: {log_summary['status']}")
        return log_summary
        
    except Exception as e:
        return {"error": str(e)}


def upload_workflow_to_n8n(workflow_json, name="AI Generated Workflow"):
    """
    최종 생성된 JS(JSON)를 n8n API를 통해 업로드합니다.
    """
    endpoint = f"{N8N_BASE_URL}/workflows"
    
    headers = {
        "X-N8N-API-KEY": N8N_API_KEY,
        "Content-Type": "application/json"
    }
    
    # n8n API 규격에 맞게 페이로드 구성
    # workflow_json은 에이전트가 만든 {"nodes": [...], "connections": {...}} 형태
    payload = {
        "name": name,
        "nodes": workflow_json.get("nodes", []),
        "connections": workflow_json.get("connections", {}),
        "settings": workflow_json.get("settings", {}),
        "staticData": workflow_json.get("staticData", None),
        "meta": workflow_json.get("meta", {}),
        "active": False # 보안을 위해 기본적으로 비활성 상태로 업로드
    }

    try:
        response = requests.post(endpoint, headers=headers, json=payload)
        response.raise_for_status()
        
        result = response.json()
        print(f"✅ 업로드 성공! Workflow ID: {result.get('id')}")
        return result
    
    except requests.exceptions.RequestException as e:
        print(f"❌ n8n 업로드 실패: {e}")
        if response is not None:
            print(f"Response: {response.text}")
        return None

def get_all_assets():
    """
    SKELETON_DIR와 COMPONENT_DIR를 모두 스캔하여 통합 맵을 반환합니다.
    결과 예: {'SKELETON_UPLOAD': 'skeletons/upload.js', 'COMPONENT_GMAIL': 'components/gmail.js'}
    """
    asset_map = {}
    for prefix, directory in BASE_DIRS.items():
        if not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
            continue
            
        for filename in os.listdir(directory):
            if filename.endswith((".txt", ".js", ".json")):
                # 파일명 기반 ID 생성 (예: SKELETON_ + UPLOAD)
                asset_id = f"{prefix}_{os.path.splitext(filename)[0].upper()}"
                asset_map[asset_id] = os.path.join(directory, filename)
    return asset_map

def extract_description(file_path):
    """
    JSON 파일 내부의 'description' 필드 또는 
    n8n 노드 중 'Sticky Note'의 내용을 설명으로 추출합니다.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            # 1. 파일이 .json인 경우 내부 데이터를 파싱
            if file_path.endswith('.json'):
                data = json.load(f)
                
                # 가짜 필드로 넣어둔 description이 있다면 최우선 반환
                if "description" in data:
                    return data["description"]
                
                # n8n 노드 중 첫 번째 Sticky Note의 내용을 설명으로 활용 (권장)
                for node in data.get("nodes", []):
                    if node.get("type") == "n8n-nodes-base.stickyNote":
                        content = node.get("parameters", {}).get("content", "")
                        # 마크다운 기호 제거 후 첫 줄만 반환
                        clean_content = content.replace("#", "").strip().split('\n')[0]
                        return clean_content
            
            # 2. 파일이 .js나 .txt인 경우 (기존 주석 로직 유지)
            else:
                f.seek(0) # 파일 포인터 초기화
                first_line = f.readline().strip()
                if first_line.startswith("// Description:"):
                    return first_line.replace("// Description:", "").strip()
                    
    except Exception as e:
        print(f"⚠️ 설명 추출 중 오류 발생 ({os.path.basename(file_path)}): {e}")

    # 설명을 찾을 수 없으면 파일명(확장자 제외)을 리턴합니다.
    return os.path.splitext(os.path.basename(file_path))[0]

def get_components_catalog():
    """
    마스터 에이전트가 호출할 함수: 모든 뼈대와 살점의 목록을 반환합니다.
    """
    catalog = []
    asset_map = get_all_assets()
    
    for asset_id, path in asset_map.items():
        description = extract_description(path)
        # ID의 시작 단어에 따라 type을 분류 (SKELETON 또는 COMPONENT)
        asset_type = "Skeleton (Core)" if asset_id.startswith("SKELETON") else "Component (Tool)"
        
        catalog.append({
            "id": asset_id,
            "type": asset_type,
            "name": os.path.basename(path),
            "description": description
        })
    return catalog

def get_file_contents(target_ids: list):
    """Target ID 리스트를 받아 실제 파일 내용들을 반환합니다."""
    asset_map = get_all_assets()
    results = []
    
    for tid in target_ids:
        path = asset_map.get(tid)
        if path and os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                # JSON 파일인 경우 불필요한 공백을 제거하고 콤팩트하게 보낼 수도 있습니다.
                if path.endswith('.json'):
                    try:
                        data = json.load(f)
                        # 에이전트에게 줄 때는 description 필드를 제외하고 순수 워크플로우만 전달 가능
                        # data.pop("description", None) 
                        results.append({"id": tid, "content": json.dumps(data, ensure_ascii=False)})
                    except json.JSONDecodeError:
                        f.seek(0)
                        results.append({"id": tid, "content": f.read()})
                else:
                    results.append({"id": tid, "content": f.read()})
        else:
            results.append({"id": tid, "content": f"ERROR: Asset {tid} not found"})
            
    return results
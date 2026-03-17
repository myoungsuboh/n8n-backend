from fastmcp import FastMCP
from typing import List, Dict, Any
from app.service.n8n_manager import (
    get_components_catalog,
    get_file_contents,
    upload_workflow_to_n8n,
    get_node_info,
    get_execution_logs
)

n8n_mcp = FastMCP("n8n Workflow Builder")

@n8n_mcp.tool(name="list_n8n_assets")
async def list_n8n_assets() -> List[Dict[str, Any]]:
    """
    n8n 워크플로우 구축에 사용할 수 있는 모든 자산(Skeleton, Component) 목록을 가져옵니다.
    에이전트가 어떤 재료(노드 묶음, 뼈대)가 있는지 확인하고 계획을 세울 때 가장 먼저 호출하세요.
    """
    return get_components_catalog()

@n8n_mcp.tool(name="read_n8n_asset_contents")
async def read_n8n_asset_contents(target_ids: List[str]) -> List[Dict[str, Any]]:
    """
    선택한 자산 ID들의 실제 내용(JSON/JS)을 읽어옵니다.
    조립할 노드의 세부 설정이나 연결 구조를 파악할 때 사용하세요.
    반환된 'content' 문자열은 유효한 JSON 포맷이며, 이를 파싱하여 워크플로우 조립에 사용하세요.
    
    Args:
        target_ids (List[str]): 읽어올 자산의 ID 리스트 (예: ['SKELETON_UPLOAD', 'COMPONENT_GMAIL'])
    """
    return get_file_contents(target_ids)

@n8n_mcp.tool(name="deploy_workflow_to_n8n")
async def deploy_workflow_to_n8n(workflow_json: Dict[str, Any], name: str = "AI Generated Workflow") -> Dict[str, Any]:
    """
    조립이 완료된 워크플로우를 실제 n8n 서버에 업로드하고 생성합니다.
    
    Args:
        workflow_data (Dict[str, Any]): nodes와 connections 필드를 반드시 포함해야 합니다.
        name (str, optional): 생성할 워크플로우의 제목입니다. 지정하지 않으면 내용을 판단하여 자동으로 생성됩니다.
    """
    result = upload_workflow_to_n8n(workflow_json, name)
    
    if result:
        return {
            "status": "success", 
            "workflow_id": result.get("id"), 
            "message": "업로드 성공"
        }
    return {"status": "error", "workflow_id": None, "message": "업로드에 실패했습니다. API 키나 URL 설정을 확인하세요."}

@n8n_mcp.tool(name="check_n8n_node_schema")
async def check_n8n_node_schema(node_type_name: str) -> Dict[str, Any]:
    """
    특정 n8n 노드의 상세 파라미터 규격(Schema)을 조회합니다.
    노드 설정값(parameters)이 정확한지 확인이 필요할 때 사용하세요.
    
    Args:
        node_type_name (str): n8n 노드 타입 이름 (예: 'n8n-nodes-base.httpRequest')
    """
    return get_node_info(node_type_name)

@n8n_mcp.tool(name="get_n8n_execution_status")
async def get_n8n_execution_status(execution_id: str) -> Dict[str, Any]:
    """
    n8n 워크플로우의 특정 실행(Execution) 결과 및 상태를 조회합니다.
    워크플로우 배포 후 실행이 성공했는지 확인하거나, 에러 발생 시 상세 원인을 파악할 때 사용합니다.
    
    Args:
        execution_id (str): 확인하려는 실행 ID (예: '12345')
    """
    # 서비스 함수가 동기(requests) 방식이므로 툴도 동기 방식으로 정의하여 
    # FastMCP의 스레드 풀에서 안전하게 실행되도록 합니다.
    return await get_execution_logs(execution_id)
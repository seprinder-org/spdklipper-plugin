from pydantic import BaseModel

class mStorage(BaseModel):
    v_id: str
    v_possessor_id: str
    v_name: str
    v_description: str
    o_cloud_path: str
    a_cloud_provider: str
    a_is_scanned: str
    a_is_optimized: str
    o_source_id: str
    v_created_timestamp: str
    v_modified_timestamp: str
    a_note: str
    a_result: str
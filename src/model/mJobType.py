from pydantic import BaseModel

class mJobType(BaseModel):
    v_id: str
    v_name: str
    v_description: str
    o_source_id: str
    v_created_timestamp: str
    v_modified_timestamp: str
    a_note: str
    a_result: str
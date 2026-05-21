from pydantic import BaseModel

class mProductGroup(BaseModel):
    v_id: str
    v_name: str
    v_description: str # String?
    o_source_id: str
    v_created_timestamp: str # DateTime @default(now())
    v_modified_timestamp: str # DateTime @default(now())
    a_note: str # String?
    a_result: str # String @default("Active")
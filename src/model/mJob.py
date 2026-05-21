from pydantic import BaseModel

class mJob(BaseModel):
    v_id: str
    v_machine_id: str
    v_possessor_id: str
    v_product_id: str
    v_job_type_id: str
    v_status: str
    o_list_frame: str
    o_secret: str
    o_source_id: str
    v_created_timestamp: str
    v_modified_timestamp: str
    a_note: str
    a_result: str
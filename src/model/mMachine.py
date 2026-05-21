from pydantic import BaseModel

class mMachine(BaseModel):
    v_id: str
    o_identify_number: str
    v_name: str
    v_machine_brand_id: str
    v_description: str
    v_status: str
    v_printing_size: str
    v_unit_size_id: str
    v_material_id: str
    v_machine_type_id: str
    v_unit_price_id: str
    v_price: float = 0.0
    v_unit_weight_id: str
    v_detail: dict
    v_possessor_id: str
    v_is_auto_eject: bool
    o_is_private: bool
    o_address_control: str
    o_address_camera: str
    o_secret: str
    o_condition: str
    o_source_id: str
    v_created_timestamp: str # Có thể dùng datetime nếu cần chuyển đổi
    v_modified_timestamp: str # Có thể dùng datetime nếu cần chuyển đổi
    a_note: str
    a_result: str